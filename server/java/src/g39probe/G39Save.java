package g39probe;

import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 用 3.9 内核重新载入并保存 .circ —— 5.0 存盘转原生 3.9 格式的标准做法
 * （source 变 3.9.0、引脚 type="output" 变 output="true"），元件/导线数量不变。
 * 用法：java -cp <jar>;<build> g39probe.G39Save <in.circ> <out.circ>
 */
public class G39Save {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### LOAD ERROR: " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        boolean ok = l.save(lf, new File(a[1]));
        System.out.println("saved=" + ok + " -> " + a[1]);
        System.exit(0);
    }
}
