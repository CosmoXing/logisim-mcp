package logisim.bridge;

import com.cburch.draw.model.AbstractCanvasObject;
import com.cburch.draw.model.CanvasObject;
import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitAttributes;
import com.cburch.logisim.circuit.CircuitMutator;
import com.cburch.logisim.circuit.CircuitTransaction;
import com.cburch.logisim.circuit.appear.AppearancePort;
import com.cburch.logisim.circuit.appear.AppearanceSvgReader;
import com.cburch.logisim.circuit.appear.CircuitAppearance;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.gui.main.Canvas;
import com.cburch.logisim.gui.main.Frame;
import com.cburch.logisim.instance.Instance;
import com.cburch.logisim.instance.StdAttr;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.proj.Projects;
import com.cburch.logisim.std.wiring.Pin;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.imageio.ImageIO;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;

/** 所有对 Logisim 内部 API 的访问都集中在这里，便于版本适配。 */
public final class LogisimAdapter {
  private static final long PROJECT_WAIT_MS = 60000;
  private File requestedFile;

  public void setRequestedFile(File file) {
    this.requestedFile = file;
  }

  public Project awaitProject() {
    return awaitProject(PROJECT_WAIT_MS);
  }

  public Project awaitProject(long timeoutMs) {
    long end = System.currentTimeMillis() + timeoutMs;
    while (System.currentTimeMillis() < end) {
      Project fallback = null;
      for (Project p : Projects.getOpenProjects()) {
        if (fallback == null) fallback = p;
        File main = mainFile(p);
        if (requestedFile == null || main == null) continue;
        try {
          if (sameFile(main, requestedFile)) return p;
        } catch (Exception ignored) {
        }
      }
      if (fallback != null && requestedFile == null) return fallback;
      if (fallback != null && mainFile(fallback) == null) return fallback;
      try {
        Thread.sleep(200);
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        break;
      }
    }
    throw new BridgeException(
        "E_NO_PROJECT",
        "Logisim 已启动但没找到打开的项目"
            + (requestedFile == null ? "" : "：" + requestedFile.getAbsolutePath()),
        "请确认文件存在且未被其他 Logisim 窗口占用",
        null);
  }

  public Frame frame(Project project) {
    Frame frame = project == null ? null : project.getFrame();
    if (frame == null) {
      throw new BridgeException("E_NO_PROJECT", "项目还没有可用的主窗口");
    }
    return frame;
  }

  public Circuit circuit(Project project, String name) {
    Circuit circuit;
    if (name == null || name.isBlank()) {
      circuit = project.getCurrentCircuit();
    } else {
      circuit = project.getLogisimFile().getCircuit(name);
    }
    if (circuit == null) {
      List<String> names = new ArrayList<>();
      for (Circuit c : project.getLogisimFile().getCircuits()) names.add(c.getName());
      throw new BridgeException(
          "E_NO_CIRCUIT", "找不到电路 " + name, "可用电路：" + String.join(", ", names), null);
    }
    return circuit;
  }

  public void selectCircuit(String name) {
    Project project = awaitProject();
    Edt.run(
        () -> {
          Circuit circuit = circuit(project, name);
          project.setCurrentCircuit(circuit);
          frame(project).repaint();
          return null;
        },
        15000);
  }

  public void showView(String view) {
    Project project = awaitProject();
    Edt.run(
        () -> {
          Frame frame = frame(project);
          String v = "appearance".equalsIgnoreCase(view) ? Frame.EDIT_APPEARANCE : Frame.EDIT_LAYOUT;
          frame.setEditorView(v);
          frame.setVisible(true);
          frame.toFront();
          frame.repaint();
          return null;
        },
        15000);
  }

  public Map<String, Object> status() {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          Frame frame = frame(project);
          Map<String, Object> m = new LinkedHashMap<>();
          m.put("pid", ProcessHandle.current().pid());
          m.put("file", path(mainFile(project)));
          m.put("circuits", circuitNames(project));
          Circuit current = project.getCurrentCircuit();
          m.put("current", current == null ? null : current.getName());
          m.put("view", frame.getEditorView());
          m.put("dirty", project.isFileDirty());
          m.put("logisim", project.getLogisimFile().getName());
          return m;
        },
        15000);
  }

  public List<Map<String, Object>> listCircuits() {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          List<Map<String, Object>> out = new ArrayList<>();
          for (Circuit c : project.getLogisimFile().getCircuits()) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("name", c.getName());
            m.put("pins", pins(c).size());
            m.put("has_custom", c.getAppearance().hasCustomAppearance());
            m.put("is_default", c.getAppearance().isDefaultAppearance());
            out.add(m);
          }
          return out;
        },
        15000);
  }

  public Map<String, Object> appearanceGet(String circuitName) {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          Circuit circuit = circuit(project, circuitName);
          CircuitAppearance appearance = circuit.getAppearance();
          Document doc = newDocument();
          List<Object> objects = new ArrayList<>();
          for (CanvasObject canvasObject : appearance.getObjectsFromBottom()) {
            if (!(canvasObject instanceof AbstractCanvasObject ac)) continue;
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("class", canvasObject.getClass().getSimpleName());
            Element el = ac.toSvgElement(doc);
            if (el != null) {
              item.put("tag", el.getTagName());
              Map<String, Object> attrs = new LinkedHashMap<>();
              NamedNodeMap map = el.getAttributes();
              for (int i = 0; i < map.getLength(); i++) {
                Node n = map.item(i);
                attrs.put(n.getNodeName(), n.getNodeValue());
              }
              item.put("attrs", attrs);
              if ("text".equals(el.getTagName())) item.put("text", el.getTextContent());
            }
            if (canvasObject instanceof AppearancePort port && port.getPin() != null) {
              item.put("pin_label", labelOf(port.getPin()));
            }
            item.put("bounds", bounds(ac));
            objects.add(item);
          }
          Map<String, Object> m = new LinkedHashMap<>();
          m.put("circuit", circuit.getName());
          m.put("is_default", appearance.isDefaultAppearance());
          m.put("has_custom", appearance.hasCustomAppearance());
          Object attr = circuit.getStaticAttributes().getValue(CircuitAttributes.APPEARANCE_ATTR);
          m.put("appearance", String.valueOf(attr));
          m.put("pins", pins(circuit));
          m.put("objects", objects);
          return m;
        },
        15000);
  }

  public Map<String, Object> appearanceApply(Map<String, Object> spec) {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          String name = Json.str(spec.get("circuit"), null);
          Circuit circuit = circuit(project, name);
          CircuitAppearance appearance = circuit.getAppearance();
          List<AppearanceSvgReader.PinInfo> pinInfos = new ArrayList<>();
          Collection<Instance> pinInstances = appearance.getCircuitPins().getPins();
          for (Instance inst : pinInstances) {
            pinInfos.add(AppearanceSvgReader.getPinInfo(inst.getLocation(), inst));
          }
          Document doc = newDocument();
          List<AbstractCanvasObject> objects = buildObjects(spec, circuit, doc, pinInfos);
          boolean allowPartial = Json.b(spec.get("allow_partial"), false);
          if (!allowPartial) {
            List<String> missing = new ArrayList<>();
            int i = 0;
            for (Instance inst : pinInstances) {
              if (!pinInfos.get(i).pinIsAlreadyUsed()) missing.add(labelOf(inst));
              i++;
            }
            if (!missing.isEmpty()) {
              throw new BridgeException(
                  "E_MISSING_PORT",
                  "外观缺少引脚端口：" + String.join(", ", missing),
                  "每个 Pin 必须恰好有一个 circ-port；可以先用 action=auto 自动生成",
                  missingDetail(missing));
            }
          }
          withTransaction(
              project,
              circuit,
              () -> {
                circuit
                    .getStaticAttributes()
                    .setValue(CircuitAttributes.APPEARANCE_ATTR, CircuitAttributes.APPEAR_CUSTOM);
                circuit
                    .getStaticAttributes()
                    .setValue(CircuitAttributes.NAMED_CIRCUIT_BOX_FIXED_SIZE, true);
                appearance.setObjectsForce(objects);
              });
          project.getLogisimFile().setDirty(true);
          frame(project).repaint();
          Map<String, Object> m = new LinkedHashMap<>();
          m.put("circuit", circuit.getName());
          m.put("objects", objects.size());
          m.put("pins", pinInstances.size());
          return m;
        },
        20000);
  }

  public Map<String, Object> appearanceReset(String circuitName, String mode) {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          Circuit circuit = circuit(project, circuitName);
          CircuitAppearance appearance = circuit.getAppearance();
          String m = mode == null ? "default_custom" : mode.toLowerCase();
          switch (m) {
            case "logisim" -> {
              withTransaction(
                  project,
                  circuit,
                  () -> {
                    circuit
                        .getStaticAttributes()
                        .setValue(CircuitAttributes.APPEARANCE_ATTR,
                            CircuitAttributes.APPEAR_EVOLUTION);
                    appearance.loadDefaultLogisimAppearance();
                  });
            }
            case "classic" -> {
              withTransaction(
                  project,
                  circuit,
                  () -> {
                    circuit
                        .getStaticAttributes()
                        .setValue(CircuitAttributes.APPEARANCE_ATTR,
                            CircuitAttributes.APPEAR_CLASSIC);
                    appearance.recomputeDefaultAppearance();
                  });
            }
            case "default_custom" -> {
              withTransaction(
                  project,
                  circuit,
                  () -> {
                    circuit
                        .getStaticAttributes()
                        .setValue(CircuitAttributes.APPEARANCE_ATTR,
                            CircuitAttributes.APPEAR_CUSTOM);
                    appearance.resetDefaultCustomAppearance();
                  });
            }
            default -> throw new BridgeException(
                "E_BAD_PARAM", "未知 reset 模式 " + m, "可选：default_custom / logisim / classic", null);
          }
          project.getLogisimFile().setDirty(true);
          frame(project).repaint();
          Map<String, Object> out = new LinkedHashMap<>();
          out.put("circuit", circuit.getName());
          out.put("mode", m);
          out.put("objects", appearance.getObjectsFromBottom().size());
          return out;
        },
        20000);
  }

  public Map<String, Object> save(File target) {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          LogisimFile file = project.getLogisimFile();
          File dest = target;
          if (dest == null) {
            dest = mainFile(project);
          }
          if (dest == null) {
            throw new BridgeException("E_SAVE_IO", "项目没有关联文件，无法保存");
          }
          Path destPath = dest.toPath().toAbsolutePath();
          Path tmp = destPath.resolveSibling(destPath.getFileName() + ".bridge-tmp");
          try (OutputStream out = new FileOutputStream(tmp.toFile())) {
            file.write(out, file.getLoader(), destPath.toFile());
          } catch (Exception e) {
            try {
              Files.deleteIfExists(tmp);
            } catch (Exception ignored) {
            }
            throw new BridgeException("E_SAVE_IO", "写入临时文件失败：" + e.getMessage(), e);
          }
          try {
            try {
              Files.move(tmp, destPath, StandardCopyOption.REPLACE_EXISTING,
                  StandardCopyOption.ATOMIC_MOVE);
            } catch (AtomicMoveNotSupportedException e) {
              Files.move(tmp, destPath, StandardCopyOption.REPLACE_EXISTING);
            }
          } catch (Exception e) {
            throw new BridgeException(
                "E_FILE_LOCKED", "替换目标文件失败：" + e.getMessage(),
                "请先关闭占用该 .circ 的其他程序", null);
          }
          file.setDirty(false);
          Map<String, Object> m = new LinkedHashMap<>();
          m.put("path", destPath.toString());
          m.put("bytes", dest.length());
          return m;
        },
        30000);
  }

  public Map<String, Object> screenshot(File out, String kind) {
    Project project = awaitProject();
    return Edt.run(
        () -> {
          Frame frame = frame(project);
          frame.setVisible(true);
          frame.validate();
          java.awt.Component target = "window".equalsIgnoreCase(kind)
              ? frame.getContentPane()
              : frame.getCanvas();
          int w = target.getWidth();
          int h = target.getHeight();
          if (w <= 0 || h <= 0) {
            throw new BridgeException("E_SCREENSHOT", "画布尺寸为 0，窗口可能还没布局完成");
          }
          BufferedImage image = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
          Graphics2D g = image.createGraphics();
          try {
            target.printAll(g);
          } finally {
            g.dispose();
          }
          File parent = out.getParentFile();
          if (parent != null && !parent.isDirectory()) parent.mkdirs();
          ImageIO.write(image, "png", out);
          Map<String, Object> m = new LinkedHashMap<>();
          m.put("path", out.getAbsolutePath());
          m.put("w", w);
          m.put("h", h);
          m.put("bytes", out.length());
          m.put("kind", kind == null ? "canvas" : kind);
          return m;
        },
        30000);
  }

  public void dispose() {
    Project project = awaitProject(3000);
    Edt.run(
        () -> {
          Frame frame = frame(project);
          frame.dispose();
          return null;
        },
        10000);
  }

  private static Map<String, Object> missingDetail(List<String> missing) {
    Map<String, Object> detail = new LinkedHashMap<>();
    detail.put("missing", missing);
    return detail;
  }

  /** 外观端口变化会改 circuit ends，且会向上影响父电路，必须锁住整个文件的所有电路。 */
  private static void withTransaction(Project project, Circuit circuit, Runnable action) {
    Map<Circuit, Integer> accessed = new LinkedHashMap<>();
    for (Circuit c : project.getLogisimFile().getCircuits()) {
      accessed.put(c, CircuitTransaction.READ_WRITE);
    }
    accessed.put(circuit, CircuitTransaction.READ_WRITE);
    new CircuitTransaction() {
      @Override
      protected Map<Circuit, Integer> getAccessedCircuits() {
        return accessed;
      }

      @Override
      protected void run(CircuitMutator mutator) {
        action.run();
      }
    }.execute();
  }

  // ------------------------------------------------------------------ 构建外观对象

  private List<AbstractCanvasObject> buildObjects(
      Map<String, Object> spec,
      Circuit circuit,
      Document doc,
      List<AppearanceSvgReader.PinInfo> pinInfos) {
    List<AbstractCanvasObject> out = new ArrayList<>();
    Map<String, Object> layout = mapOrEmpty(spec.get("layout"));
    Map<String, Object> anchor = mapOrEmpty(layout.get("anchor"));
    String facing = Json.str(anchor.get("facing"), "east");
    out.add(shape(doc, pinInfos, circuit, "circ-anchor",
        attrs("x", Json.i(anchor.get("x"), 0), "y", Json.i(anchor.get("y"), 0), "facing", facing)));

    int width = Json.i(layout.get("width"), 0);
    int height = Json.i(layout.get("height"), 0);
    int boxX = Json.i(layout.get("x"), 0);
    int boxY = Json.i(layout.get("y"), 0);
    if (width <= 0 || height <= 0) {
      throw new BridgeException("E_BAD_BOX", "layout.width/height 必须是正数");
    }
    int radius = Json.i(layout.get("corner_radius"), 0);
    Map<String, Object> boxStyle = mapOrEmpty(layout.get("box"));
    Map<String, Object> boxAttrs = attrs(
        "x", boxX, "y", boxY, "width", width, "height", height,
        "stroke", Json.str(boxStyle.get("stroke"), "#000000"),
        "fill", Json.str(boxStyle.get("fill"), "none"),
        "stroke-width", Json.i(boxStyle.get("stroke_width"), 2));
    if (radius > 0) boxAttrs.put("rx", radius);
    out.add(shape(doc, pinInfos, circuit, radius > 0 ? "rect" : "rect", boxAttrs));

    Map<String, Object> plate = mapOrEmpty(layout.get("nameplate"));
    if (Json.b(plate.get("enabled"), false)) {
      int plateH = Json.i(plate.get("height"), 20);
      int plateY = boxY + height - plateH;
      String fill = Json.str(plate.get("fill"), "#000000");
      String textColor = Json.str(plate.get("text_color"), "#FFFFFF");
      out.add(shape(doc, pinInfos, circuit, "rect", attrs(
          "x", boxX, "y", plateY, "width", width, "height", plateH,
          "stroke", "none", "fill", fill)));
      String text = Json.str(plate.get("text"), circuit.getName());
      int fontSize = Json.i(plate.get("font_size"), 12);
      out.add(textElement(doc, pinInfos, circuit,
          boxX + width / 2, plateY + plateH / 2, text,
          textColor, fontSize, Json.b(plate.get("bold"), true), "center", "middle"));
    }

    Map<String, Object> labelOpt = mapOrEmpty(layout.get("port_labels"));
    if (Json.b(labelOpt.get("enabled"), true)) {
      int offset = Json.i(labelOpt.get("offset"), 8);
      int fontSize = Json.i(labelOpt.get("font_size"), 11);
      boolean showWidth = Json.b(labelOpt.get("show_width"), true);
      for (Object item : listOrEmpty(spec.get("ports"))) {
        Map<String, Object> p = Json.obj(item);
        String label = Json.str(p.get("label"), Json.str(p.get("pin"), ""));
        int bw = Json.i(p.get("width"), 1);
        String text = label + (showWidth && bw > 1 ? "[" + bw + "]" : "");
        boolean left = "left".equalsIgnoreCase(Json.str(p.get("side"), "left"));
        int x = Json.i(p.get("x"), 0) + (left ? offset : -offset);
        int y = Json.i(p.get("y"), 0);
        out.add(textElement(doc, pinInfos, circuit, x, y, text, "#000000", fontSize, false,
            left ? "start" : "end", "middle"));
      }
    }

    for (Object item : listOrEmpty(spec.get("texts"))) {
      Map<String, Object> t = Json.obj(item);
      out.add(textElement(doc, pinInfos, circuit,
          Json.i(t.get("x"), 0), Json.i(t.get("y"), 0), Json.str(t.get("text"), ""),
          Json.str(t.get("fill"), "#000000"), Json.i(t.get("font_size"), 12),
          Json.b(t.get("bold"), false), Json.str(t.get("halign"), "center"),
          Json.str(t.get("valign"), "middle")));
    }

    for (Object item : listOrEmpty(spec.get("shapes"))) {
      Map<String, Object> s = Json.obj(item);
      String type = Json.str(s.get("type"), "").toLowerCase();
      Map<String, Object> a = new LinkedHashMap<>();
      switch (type) {
        case "rect", "roundrect" -> {
          a.put("x", Json.i(s.get("x"), 0));
          a.put("y", Json.i(s.get("y"), 0));
          a.put("width", Json.i(s.get("w"), Json.i(s.get("width"), 0)));
          a.put("height", Json.i(s.get("h"), Json.i(s.get("height"), 0)));
          a.put("stroke", Json.str(s.get("stroke"), "#000000"));
          a.put("fill", Json.str(s.get("fill"), "none"));
          if ("roundrect".equals(type)) a.put("rx", Json.i(s.get("radius"), 10));
        }
        case "line" -> {
          a.put("x1", Json.i(s.get("x1"), 0));
          a.put("y1", Json.i(s.get("y1"), 0));
          a.put("x2", Json.i(s.get("x2"), 0));
          a.put("y2", Json.i(s.get("y2"), 0));
          a.put("stroke", Json.str(s.get("stroke"), "#000000"));
        }
        case "ellipse" -> {
          a.put("cx", Json.i(s.get("cx"), 0));
          a.put("cy", Json.i(s.get("cy"), 0));
          a.put("rx", Json.i(s.get("rx"), 0));
          a.put("ry", Json.i(s.get("ry"), 0));
          a.put("stroke", Json.str(s.get("stroke"), "#000000"));
          a.put("fill", Json.str(s.get("fill"), "none"));
        }
        case "polyline", "polygon" -> {
          a.put("points", Json.str(s.get("points"), ""));
          a.put("stroke", Json.str(s.get("stroke"), "#000000"));
          a.put("fill", "polygon".equals(type) ? Json.str(s.get("fill"), "none") : "none");
        }
        case "text" -> {
          out.add(textElement(doc, pinInfos, circuit,
              Json.i(s.get("x"), 0), Json.i(s.get("y"), 0), Json.str(s.get("text"), ""),
              Json.str(s.get("fill"), "#000000"), Json.i(s.get("font_size"), 12),
              Json.b(s.get("bold"), false), Json.str(s.get("halign"), "center"),
              Json.str(s.get("valign"), "middle")));
          continue;
        }
        default -> throw new BridgeException(
            "E_UNSUPPORTED_SHAPE", "不支持的形状 " + type,
            "第一版支持 rect/roundrect/line/ellipse/polyline/polygon/text", null);
      }
      out.add(shape(doc, pinInfos, circuit, type.equals("roundrect") ? "rect" : type, a));
    }

    for (Object item : listOrEmpty(spec.get("ports"))) {
      Map<String, Object> p = Json.obj(item);
      Instance pin = resolvePin(p, pinInfos, circuit);
      String dir = Json.str(p.get("dir"), null);
      if (dir == null) dir = Pin.FACTORY.isInputPin(pin) ? "in" : "out";
      Map<String, Object> a = attrs(
          "x", Json.i(p.get("x"), 0),
          "y", Json.i(p.get("y"), 0),
          "dir", "out".equalsIgnoreCase(dir) ? "out" : "in",
          "pin", pin.getLocation().getX() + "," + pin.getLocation().getY());
      out.add(shape(doc, pinInfos, circuit, "circ-port", a));
    }
    return out;
  }

  private Instance resolvePin(
      Map<String, Object> port, List<AppearanceSvgReader.PinInfo> pinInfos, Circuit circuit) {
    String label = Json.str(port.get("pin"), "");
    String pinAt = Json.str(port.get("pin_at"), "");
    List<Instance> matches = new ArrayList<>();
    for (AppearanceSvgReader.PinInfo info : pinInfos) {
      Instance inst = info.getPinInstance();
      if (label != null && !label.equals(labelOf(inst))) continue;
      if (pinAt != null && !pinAt.isBlank()) {
        Location loc = inst.getLocation();
        if (!pinAt.equals(loc.getX() + "," + loc.getY())) continue;
      }
      matches.add(inst);
    }
    if (matches.isEmpty()) {
      throw new BridgeException(
          "E_NO_PIN", "电路 " + circuit.getName() + " 里没有引脚 " + label,
          "引脚标签区分大小写；可先用 circ_appearance get 查看 pins", null);
    }
    if (matches.size() > 1) {
      throw new BridgeException(
          "E_AMBIGUOUS_PIN", "引脚标签 " + label + " 对应多个 Pin，需要提供 pin_at",
          "pin_at 形如 \"120,200\"，取自原理图中 Pin 的 loc", null);
    }
    return matches.get(0);
  }

  private AbstractCanvasObject shape(
      Document doc,
      List<AppearanceSvgReader.PinInfo> pinInfos,
      Circuit circuit,
      String tag,
      Map<String, Object> attributes) {
    Element el = doc.createElement(tag);
    for (Map.Entry<String, Object> e : attributes.entrySet()) {
      el.setAttribute(e.getKey(), String.valueOf(e.getValue()));
    }
    AbstractCanvasObject obj = AppearanceSvgReader.createShape(el, pinInfos, circuit);
    if (obj == null) {
      throw new BridgeException(
          "E_PORT_UNMATCHED", "外观元素 " + tag + " 无法被 Logisim 解析",
          "circ-port 的 pin 坐标/方向必须与原理图 Pin 一致", null);
    }
    return obj;
  }

  private AbstractCanvasObject textElement(
      Document doc,
      List<AppearanceSvgReader.PinInfo> pinInfos,
      Circuit circuit,
      int x,
      int y,
      String text,
      String fill,
      int fontSize,
      boolean bold,
      String halign,
      String valign) {
    Element el = doc.createElement("text");
    el.setAttribute("x", String.valueOf(x));
    el.setAttribute("y", String.valueOf(y));
    el.setAttribute("fill", fill);
    el.setAttribute("font-family", "SansSerif");
    el.setAttribute("font-size", String.valueOf(fontSize));
    if (bold) el.setAttribute("font-weight", "bold");
    el.setAttribute("text-anchor",
        "start".equals(halign) ? "start" : ("end".equals(halign) ? "end" : "middle"));
    el.setAttribute("dominant-baseline",
        "top".equals(valign) ? "top" : ("bottom".equals(valign) ? "bottom" : "middle"));
    el.setTextContent(text == null ? "" : text);
    AbstractCanvasObject obj = AppearanceSvgReader.createShape(el, pinInfos, circuit);
    if (obj == null) {
      throw new BridgeException("E_INTERNAL", "无法创建文本对象 " + text);
    }
    return obj;
  }

  // ------------------------------------------------------------------ 读模型辅助

  private List<Map<String, Object>> pins(Circuit circuit) {
    List<Map<String, Object>> out = new ArrayList<>();
    for (Instance inst : circuit.getAppearance().getCircuitPins().getPins()) {
      Map<String, Object> m = new LinkedHashMap<>();
      m.put("label", labelOf(inst));
      m.put("at", inst.getLocation().getX() + "," + inst.getLocation().getY());
      m.put("dir", Pin.FACTORY.isInputPin(inst) ? "in" : "out");
      BitWidth width = inst.getAttributeValue(StdAttr.WIDTH);
      m.put("width", width == null ? 1 : width.getWidth());
      out.add(m);
    }
    return out;
  }

  private static String labelOf(Instance inst) {
    String label = inst.getAttributeValue(StdAttr.LABEL);
    return label == null ? "" : label;
  }

  private static Map<String, Object> bounds(AbstractCanvasObject obj) {
    var b = obj.getBounds();
    Map<String, Object> m = new LinkedHashMap<>();
    m.put("x", b.getX());
    m.put("y", b.getY());
    m.put("w", b.getWidth());
    m.put("h", b.getHeight());
    return m;
  }

  private List<String> circuitNames(Project project) {
    List<String> names = new ArrayList<>();
    for (Circuit c : project.getLogisimFile().getCircuits()) names.add(c.getName());
    return names;
  }

  private static File mainFile(Project project) {
    try {
      LogisimFile file = project.getLogisimFile();
      if (file == null || file.getLoader() == null) return null;
      return file.getLoader().getMainFile();
    } catch (Exception e) {
      return null;
    }
  }

  private static boolean sameFile(File a, File b) {
    try {
      return a.getCanonicalFile().equals(b.getCanonicalFile());
    } catch (Exception e) {
      return a.getAbsoluteFile().equals(b.getAbsoluteFile());
    }
  }

  private static String path(File f) {
    return f == null ? null : f.getAbsolutePath();
  }

  private static Document newDocument() {
    try {
      return DocumentBuilderFactory.newInstance().newDocumentBuilder().newDocument();
    } catch (Exception e) {
      throw new BridgeException("E_INTERNAL", "创建 XML 文档失败：" + e.getMessage(), e);
    }
  }

  private static Map<String, Object> attrs(Object... kv) {
    Map<String, Object> m = new LinkedHashMap<>();
    for (int i = 0; i + 1 < kv.length; i += 2) m.put(String.valueOf(kv[i]), kv[i + 1]);
    return m;
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> mapOrEmpty(Object v) {
    return v instanceof Map ? (Map<String, Object>) v : new LinkedHashMap<>();
  }

  @SuppressWarnings("unchecked")
  private static List<Object> listOrEmpty(Object v) {
    return v instanceof List ? (List<Object>) v : new ArrayList<>();
  }
}
