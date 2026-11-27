package g40probe;

import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 用 4.0 内核重新载入并保存 .circ —— 得到原生 4.0 格式
 * （source 变 4.0.0、库索引改成 0~4、toolbar/mappings 的 tool 带 lib 属性）。
 * 用法：java -cp <4.0 jar>;<build> g40probe.G40Save <in.circ> <out.circ>
 */
public class G40Save {
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