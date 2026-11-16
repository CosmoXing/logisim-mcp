import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

public class LoadTest {
    static class MyLoader extends Loader {
        MyLoader() { super(null); }
        @Override public void showError(String message) {
            System.out.println("SHOWERROR: " + message);
        }
    }

    public static void main(String[] args) throws Exception {
        MyLoader loader = new MyLoader();
        LogisimFile f = loader.openLogisimFile(new File(args[0]));
        if (f == null) {
            System.out.println("NULL FILE");
        } else {
            System.out.println("LOADED " + f.getCircuits().size() + " circuits");
        }
    }
}
