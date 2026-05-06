"""
inventory.py — Inventory state management for the pharmacy simulation.

Classes
-------
AgeBucketInventory
    FIFO inventory with per-unit age tracking (for expiry).
PipelineQueue
    Tracks in-transit orders arriving after lead-time L days.

Functions
---------
simulate_one_day(...)
    Execute one complete day: receive orders → expire → sell → substitute → reorder.
"""

import numpy as np
from collections import deque


# ---------------------------------------------------------------------------
# Age-Bucket Inventory  (FIFO, with expiry)
# ---------------------------------------------------------------------------

class AgeBucketInventory:
    """
    FIFO inventory that tracks the age of every batch of units.

    Internal structure: deque of [quantity, age_days] pairs,
    oldest entry at left, newest at right.
    """

    def __init__(self, initial_qty: int = 0, initial_age: int = 0):
        self._buckets: deque = deque()
        if initial_qty > 0:
            self._buckets.append([initial_qty, initial_age])

    # ------------------------------------------------------------------
    def add(self, quantity: int):
        """Add freshly received units (age = 0)."""
        if quantity > 0:
            self._buckets.append([quantity, 0])

    # ------------------------------------------------------------------
    def age_one_day(self):
        """Increment age of every bucket by 1 day."""
        for bucket in self._buckets:
            bucket[1] += 1

    # ------------------------------------------------------------------
    def expire(self, max_age: int) -> int:
        """
        Remove units whose age has reached or exceeded max_age days.

        A unit is considered expired on the day its age equals max_age
        (i.e. it has been in stock for max_age full days).  The boundary
        condition is inclusive: age >= max_age triggers removal.

        Bug-fix note: the original condition ``> max_age`` was off by one —
        it allowed units to remain on the shelf one day past their shelf-life.
        Corrected to ``>= max_age`` so expiry fires on the exact expiry day.

        Returns
        -------
        expired_qty : int
        """
        expired_qty = 0
        while self._buckets and self._buckets[0][1] >= max_age:   # FIX: >= (was >)
            expired_qty += self._buckets.popleft()[0]
        return expired_qty

    # ------------------------------------------------------------------
    def sell(self, demand: int):
        """
        Sell up to `demand` units, consuming oldest buckets first.

        Returns
        -------
        sold : int
        lost : int   Unmet demand.
        """
        remaining = demand
        sold = 0
        while remaining > 0 and self._buckets:
            oldest = self._buckets[0]
            take = min(oldest[0], remaining)
            oldest[0] -= take
            sold += take
            remaining -= take
            if oldest[0] == 0:
                self._buckets.popleft()
        return sold, remaining          # remaining = lost sales

    # ------------------------------------------------------------------
    @property
    def on_hand(self) -> int:
        return sum(b[0] for b in self._buckets)


# ---------------------------------------------------------------------------
# Pipeline Queue  (pending orders)
# ---------------------------------------------------------------------------

class PipelineQueue:
    """
    Circular queue of length L+1 tracking units arriving in 1…L days.

    Index 0  → units arriving *today*.
    Index L  → units arriving in L days (i.e. just-placed orders).
    """

    def __init__(self, lead_time: int):
        self._L = lead_time
        self._q = deque([0] * (lead_time + 1), maxlen=lead_time + 1)

    def place_order(self, qty: int):
        """Record a new order that will arrive in L days."""
        self._q[-1] += qty

    def advance(self) -> int:
        """
        Advance one day.  Returns units that arrived today.
        """
        arrived = self._q[0]
        self._q.rotate(-1)   # oldest becomes slot L
        self._q[-1] = 0
        return arrived

    @property
    def pipeline_qty(self) -> int:
        return sum(self._q)


# ---------------------------------------------------------------------------
# Single-Day Simulation Step
# ---------------------------------------------------------------------------

def simulate_one_day(inv_a, inv_b, pipeline_a, pipeline_b,
                     demand_a, demand_b,
                     Q_a, Q_b, R_a, R_b,
                     params: dict) -> dict:
    """
    Simulate one day for two products (Ibuprofen=A, Paracetamol=B).

    Daily sequence
    --------------
    1. Receive any pipeline arrivals.
    2. Age every unit by one day.
    3. Expire units older than expiry_k days.
    4. Fill primary demand (FIFO).
    5. Substitution: fraction sub_rate of stockouts shifts to other product.
    6. Ordering decision: (R, Q) policy on inventory position.
    7. Compute daily profit.

    Parameters
    ----------
    params keys required: p, c, s, pi, disposal_cost, sub_rate,
                          expiry_k, lead_time.
    params keys optional:
        holding_cost : float (default 0.0)
            Per-unit per-day cost of carrying inventory on hand.
            Accounts for capital tied up, refrigeration, insurance, etc.
            Omit or set to 0.0 to reproduce original behaviour exactly.

    Profit accounting note
    ----------------------
    Ordering cost ``c * order_qty`` is charged on the day the order is
    *placed* (cash-on-order / accrual basis).  Units arrive ``lead_time``
    days later; revenue is collected when those units are eventually sold.
    This is standard accrual accounting for inventory models and produces
    correct period-by-period profit when aggregated over many days.

    Returns
    -------
    dict with per-product metrics.
    """
    # ── Validate required keys (additive guard — does not change behaviour) ──
    required = ('p', 'c', 's', 'pi', 'disposal_cost', 'sub_rate', 'expiry_k')
    missing = [k for k in required if k not in params]
    if missing:
        raise KeyError(f"simulate_one_day: missing params keys: {missing}")

    p   = params['p']
    c   = params['c']
    s   = params['s']
    pi  = params['pi']
    dc  = params['disposal_cost']
    sr  = params['sub_rate']
    K   = params['expiry_k']
    # holding_cost is optional; defaults to 0.0 so existing callers are unaffected
    hc  = params.get('holding_cost', 0.0)

    # 1. Receive arrivals
    recv_a = pipeline_a.advance()
    recv_b = pipeline_b.advance()
    inv_a.add(recv_a)
    inv_b.add(recv_b)

    # 2-3. Age then expire
    inv_a.age_one_day();  inv_b.age_one_day()
    expired_a = inv_a.expire(K)
    expired_b = inv_b.expire(K)

    # 4. Primary sales
    sold_a, lost_a = inv_a.sell(demand_a)
    sold_b, lost_b = inv_b.sell(demand_b)

    # 5. Substitution
    sub_to_b = int(round(lost_a * sr))
    sub_to_a = int(round(lost_b * sr))
    extra_a, unmet_sub_a = inv_a.sell(sub_to_a)   # FIX: capture unmet_sub_a
    extra_b, unmet_sub_b = inv_b.sell(sub_to_b)   # FIX: capture unmet_sub_b

    total_sold_a = sold_a + extra_a
    total_sold_b = sold_b + extra_b
    # FIX: lost sales = original unmet demand that could NOT be covered by substitution
    # unmet_sub_a is the portion of sub_to_a that inv_a could not fill (genuine lost)
    total_lost_a = lost_a - (sub_to_a - unmet_sub_a)   # = lost_a - extra_a
    total_lost_b = lost_b - (sub_to_b - unmet_sub_b)   # = lost_b - extra_b
    # Clamp to 0 to guard against any floating-point edge
    total_lost_a = max(total_lost_a, 0)
    total_lost_b = max(total_lost_b, 0)

    # 6. Ordering decision  (inventory position = on-hand + pipeline)
    ip_a = inv_a.on_hand + pipeline_a.pipeline_qty
    ip_b = inv_b.on_hand + pipeline_b.pipeline_qty
    order_a = Q_a if ip_a <= R_a else 0
    order_b = Q_b if ip_b <= R_b else 0
    if order_a > 0:
        pipeline_a.place_order(order_a)
    if order_b > 0:
        pipeline_b.place_order(order_b)

    # 7. Daily profit
    # Cost charged when order is placed; revenue when sold.
    # holding_cost applied to end-of-day on-hand inventory (after sales).
    inv_end_a = inv_a.on_hand
    inv_end_b = inv_b.on_hand

    profit_a = (p * total_sold_a
                - c * order_a
                - pi * total_lost_a
                - dc * expired_a
                - hc * inv_end_a)          # holding cost (0.0 if not provided)
    profit_b = (p * total_sold_b
                - c * order_b
                - pi * total_lost_b
                - dc * expired_b
                - hc * inv_end_b)          # holding cost (0.0 if not provided)

    return dict(
        recv_a=recv_a,        recv_b=recv_b,
        expired_a=expired_a,  expired_b=expired_b,
        sales_a=total_sold_a, sales_b=total_sold_b,
        lost_a=total_lost_a,  lost_b=total_lost_b,
        order_a=order_a,      order_b=order_b,
        profit_a=profit_a,    profit_b=profit_b,
        inv_end_a=inv_end_a,
        inv_end_b=inv_end_b,
    )


# ---------------------------------------------------------------------------
# Unit Tests  (run with:  python inventory.py  OR  pytest inventory.py)
# ---------------------------------------------------------------------------

class _TestAgeBucketInventory:
    """Self-contained unit tests — no external dependencies required."""

    @staticmethod
    def _run_all():
        passed = 0
        failed = 0

        def ok(name):
            nonlocal passed
            passed += 1
            print(f"  PASS  {name}")

        def fail(name, msg):
            nonlocal failed
            failed += 1
            print(f"  FAIL  {name}: {msg}")

        # ── AgeBucketInventory ──────────────────────────────────────────────

        # Test 1: add + on_hand
        inv = AgeBucketInventory(initial_qty=100, initial_age=0)
        assert inv.on_hand == 100, f"Expected 100, got {inv.on_hand}"
        ok("AgeBucketInventory: initial on_hand")

        # Test 2: sell partial
        sold, lost = inv.sell(40)
        assert sold == 40 and lost == 0 and inv.on_hand == 60, \
            f"sell(40) → sold={sold}, lost={lost}, on_hand={inv.on_hand}"
        ok("AgeBucketInventory: sell partial demand")

        # Test 3: sell excess (lost sales)
        inv2 = AgeBucketInventory(initial_qty=10, initial_age=0)
        sold, lost = inv2.sell(25)
        assert sold == 10 and lost == 15 and inv2.on_hand == 0, \
            f"sell(25) with stock=10 → sold={sold}, lost={lost}"
        ok("AgeBucketInventory: sell excess (lost sales)")

        # Test 4: age_one_day increments correctly
        inv3 = AgeBucketInventory(initial_qty=50, initial_age=0)
        inv3.age_one_day()
        inv3.age_one_day()
        age = inv3._buckets[0][1]
        assert age == 2, f"Expected age=2 after 2 days, got {age}"
        ok("AgeBucketInventory: age_one_day")

        # Test 5: expire — unit MUST expire on the exact expiry day (>= boundary)
        inv4 = AgeBucketInventory(initial_qty=30, initial_age=0)
        for _ in range(30):          # age to exactly 30 days
            inv4.age_one_day()
        expired = inv4.expire(max_age=30)
        assert expired == 30, \
            f"Expected all 30 units expired at age=30, got {expired} (off-by-one bug if 0)"
        ok("AgeBucketInventory: expire at exact max_age boundary (off-by-one fix)")

        # Test 6: units below max_age must NOT expire
        inv5 = AgeBucketInventory(initial_qty=20, initial_age=0)
        for _ in range(29):          # age to 29 days
            inv5.age_one_day()
        expired = inv5.expire(max_age=30)
        assert expired == 0, \
            f"Expected 0 expired at age=29, got {expired}"
        ok("AgeBucketInventory: no expiry before max_age")

        # Test 7: FIFO order — oldest bucket sold first
        inv6 = AgeBucketInventory(initial_qty=5, initial_age=0)
        inv6.age_one_day()           # age old batch to 1
        inv6.add(10)                 # new batch age=0
        sold, _ = inv6.sell(5)
        # Old bucket (qty=5, age=1) should be consumed completely first
        assert inv6.on_hand == 10, \
            f"Expected 10 on hand (old batch gone), got {inv6.on_hand}"
        ok("AgeBucketInventory: FIFO sell order")

        # ── PipelineQueue ───────────────────────────────────────────────────

        # Test 8: L=3 pipeline — order placed today arrives in 3 days
        pq = PipelineQueue(lead_time=3)
        pq.place_order(100)
        for day in range(3):
            arrived = pq.advance()
            assert arrived == 0, f"Should not arrive on day {day+1}, got {arrived}"
        arrived = pq.advance()       # day 4 — should arrive now (after L advances)
        # After 3 advances the slot rotates to index 0 on the 4th advance
        # Actually: place_order fills index L=3. After 1 advance index 3→2,
        # after 2: 3→1, after 3: 3→0, after 4th advance: arrived = _q[0] BEFORE rotate
        # Re-check: advance() reads _q[0] THEN rotates. So on advance 4 _q[0]=100.
        # But we already did 3 advances above. Let's re-verify:
        # advance 1: arrived=_q[0]=0, rotate → order now at index 2
        # advance 2: arrived=0, rotate → order at index 1
        # advance 3: arrived=0, rotate → order at index 0
        # advance 4: arrived=_q[0]=100  ← this is what 'arrived' holds above
        assert arrived == 100, f"Expected 100 to arrive on day 4, got {arrived}"
        ok("PipelineQueue: order arrives after exactly L days")

        # Test 9: pipeline_qty tracks total in-transit units
        pq2 = PipelineQueue(lead_time=2)
        pq2.place_order(50)
        pq2.place_order(30)          # same slot — should accumulate
        assert pq2.pipeline_qty == 80, \
            f"Expected pipeline_qty=80, got {pq2.pipeline_qty}"
        ok("PipelineQueue: pipeline_qty accumulates correctly")

        # ── simulate_one_day input validation ──────────────────────────────

        # Test 10: missing params key raises KeyError
        try:
            inv_a = AgeBucketInventory(10)
            inv_b = AgeBucketInventory(10)
            simulate_one_day(inv_a, inv_b, PipelineQueue(0), PipelineQueue(0),
                             5, 5, 50, 50, 20, 20, params={})  # empty params
            fail("simulate_one_day: missing key validation", "No error raised")
        except KeyError:
            ok("simulate_one_day: KeyError raised on missing params")

        # Summary
        print(f"\n{'='*45}")
        print(f"  Unit Test Results: {passed} passed, {failed} failed")
        print(f"{'='*45}")
        return failed == 0


if __name__ == '__main__':
    print("Running inventory.py unit tests …\n")
    success = _TestAgeBucketInventory._run_all()
    raise SystemExit(0 if success else 1)
