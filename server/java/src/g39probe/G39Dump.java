package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 打印一个电路里全部 Pin 加载后的真实属性（label/width/output/radix/三态等）。
 * 用来确认 5.0 的 type="output" 写法被 3.9 正确读成 output=true、
 * 以及 radix 修改是否生效。
 * 用法：java -cp <jar>;<build> g39probe.G39Dump <file.circ> <circuit>
 */
public class G39Dump {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        for (Component comp : c.getNonWires()) {
            if (!comp.getFactory().getName().equals("Pin")) continue;
            StringBuilder sb = new StringBuilder(comp.getFactory().getName() + " @ " + comp.getLocation() + " -> ");
            for (Attribute<?> at : comp.getAttributeSet().getAttributes())
                sb.append(at.getName()).append('=').append(comp.getAttributeSet().getValue(at)).append("  ");
            System.out.println(sb);
        }
        System.exit(0);
    }
}
