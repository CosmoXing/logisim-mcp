package g40probe;

import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 用 Logisim-evolution 4.0 内核真实加载 .circ，打印加载错误与电路清单。
 * 用法：java -cp <4.0 jar>;<build> g40probe.G40Check <file.circ>
 */
public class G40Check {
    public static void main(String[] a) throws Exception {
        Loader loader = new Loader(null) {
            @Override public void showError(String msg) {
                System.out.println("### LOAD ERROR: " + msg);
            }
        };
        LogisimFile lf = loader.openLogisimFile(new File(a[0]));
        System.out.println("loaded circuits=" + lf.getCircuits().size()
                + " main=" + (lf.getMainCircuit() == null ? "?" : lf.getMainCircuit().getName()));
        for (var c : lf.getCircuits()) System.out.println("  - " + c.getName());
        System.exit(0);
    }
}