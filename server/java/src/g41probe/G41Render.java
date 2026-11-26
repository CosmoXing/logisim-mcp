package g41probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.ComponentDrawContext;
import com.cburch.logisim.data.Bounds;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;

/**
 * 把 4.1 的某个电路无头渲染成 PNG（给实验报告截图用）。
 * 用法：java -cp <4.1 jar>;<build> g41probe.G41Render <file.circ> <circuit> <out.png> [scale]
 * scale 默认 2（2 倍像素，插入 Word 后清晰）。
 */
public class G41Render {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        if (c == null) {
            System.out.println("no such circuit: " + a[1]);
            System.exit(1);
        }
        double scale = a.length > 3 ? Double.parseDouble(a[3]) : 2.0;

        BufferedImage probe = new BufferedImage(1, 1, BufferedImage.TYPE_INT_ARGB);
        Graphics2D pg = probe.createGraphics();
        Bounds b = c.getBounds(pg);
        pg.dispose();

        int margin = 24;
        int w = (int) Math.ceil((b.getWidth() + 2 * margin) * scale);
        int h = (int) Math.ceil((b.getHeight() + 2 * margin) * scale);
        BufferedImage img = new BufferedImage(Math.max(w, 40), Math.max(h, 40),
                BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, img.getWidth(), img.getHeight());
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING,
                RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL,
                RenderingHints.VALUE_STROKE_PURE);
        g.scale(scale, scale);
        g.translate(-b.getX() + margin, -b.getY() + margin);

        ComponentDrawContext ctx = new ComponentDrawContext(null, c, null, g, g);
        ctx.setShowState(false);
        for (Wire wire : c.getWires()) wire.draw(ctx);
        for (Component comp : c.getNonWires()) comp.draw(ctx);
        g.dispose();

        File out = new File(a[2]);
        ImageIO.write(img, "png", out);
        System.out.println("rendered " + a[1] + " -> " + out.getAbsolutePath()
                + " " + img.getWidth() + "x" + img.getHeight());
        System.exit(0);
    }
}
