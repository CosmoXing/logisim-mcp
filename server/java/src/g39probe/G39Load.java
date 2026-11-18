package g39probe;

import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 用 Logisim 3.9 内核真实加载 .circ，打印所有加载错误与电路清单。
 * 用法：java -cp <jar>;<build> g39probe.G39Load <file.circ>
 * 5.0 文件在 3.9 打不开时，这里会给出 GUI 弹窗里的同款错误
 * （典型：`<mappings>/<toolbar>` 的 <tool> 缺 lib 属性）。
 */
public class G39Load {
    public static void main(String[] a) throws Exception {
        Loader loader = new Loader(null) {
            @Override public void showError(String msg) {
                System.out.println("### LOAD ERROR: " + msg);
            }
        };
        LogisimFile lf = loader.openLogisimFile(new File(a[0]));
        System.out.println("loaded circuits=" + lf.getCircuits().size());
        for (var c : lf.getCircuits()) System.out.println("  - " + c.getName());
        System.exit(0);
    }
}
