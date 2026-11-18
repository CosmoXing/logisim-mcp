import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.tools.SetAttributeAction;
import com.cburch.logisim.util.StringGetter;

/**
 * 触发一次「改属性」动作（与界面里 TextTool 提交文字同一条路径：
 * SetAttributeAction → CircuitTransaction → WireRepair），用来验证
 * 「改文字就卡死」是否复现。
 *
 * 用法：java AttrProbe <circ 文件> [电路名]
 * 输出：ATTR_OK <耗时ms> / NO_TEXT_COMPONENT / NO_TEXT_ATTR
 *
 * 注意：Logisim 的 Simulator 线程是非 daemon，main 结束后进程不会自己退出，
 * 所以调用方应轮询标准输出里是否出现 ATTR_OK，然后主动 kill。
 */
public class AttrProbe {
    public static void main(String[] args) throws Exception {
        Loader loader = new Loader(null);
        LogisimFile f = loader.openLogisimFile(new java.io.File(args[0]));
        String cname = args.length > 1 ? args[1] : "main";
        Circuit c = f.getCircuit(cname);
        Project proj = new Project(f);

        Component target = null;
        for (Component comp : c.getNonWires()) {
            if ("Text".equals(comp.getFactory().getName())) {
                target = comp;
                break;
            }
        }
        if (target == null) {
            System.out.println("NO_TEXT_COMPONENT");
            return;
        }
        Attribute<?> attr = null;
        for (Attribute<?> a : target.getAttributeSet().getAttributes()) {
            if ("text".equals(a.getName())) {
                attr = a;
                break;
            }
        }
        if (attr == null) {
            System.out.println("NO_TEXT_ATTR");
            return;
        }
        StringGetter desc = new StringGetter() {
            public String get() {
                return "attrprobe";
            }
        };
        SetAttributeAction act = new SetAttributeAction(c, desc);
        act.set(target, attr, "probe-" + System.nanoTime());
        long t0 = System.currentTimeMillis();
        proj.doAction(act);
        System.out.println("ATTR_OK " + (System.currentTimeMillis() - t0) + "ms");
    }
}