path = r'c:\Users\Mayer_R\Downloads\Simulation_Project (2)\Simulation_Project\simu_updated\frontend\src\components\Dashboard.jsx'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: sidebar closing + main content opening
old1 = '        </form>\n      </div>\n\n      {/* Main Content Area - Ref for PDF */}\n      <div className="flex-1 space-y-6" ref={dashboardRef}>'
new1 = '          </form>\n        </motion.div>\n\n        {/* Main Content Area */}\n        <motion.div variants={item} className="flex-1 space-y-6" ref={dashboardRef}>'

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Fix 1 applied.")
else:
    # Try to find what's there
    idx = content.find('</form>')
    print("Fix 1 NOT found. Context:", repr(content[idx-10:idx+120]))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done.")
