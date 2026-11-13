package logisim.bridge;

import java.io.File;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 命令分派：只做参数提取与转发，Logisim API 都在 LogisimAdapter。 */
public final class Commands {
  public static final String VERSION = "0.1.0";
  private final LogisimAdapter adapter;

  public Commands(LogisimAdapter adapter) {
    this.adapter = adapter;
  }

  public Map<String, Object> handle(String cmd, Map<String, Object> params) {
    switch (cmd) {
      case "ping" -> {
        return map("pong", true, "version", VERSION, "pid", ProcessHandle.current().pid());
      }
      case "status" -> {
        return adapter.status();
      }
      case "list_circuits" -> {
        return map("circuits", adapter.listCircuits());
      }
      case "select_circuit" -> {
        String circuit = str(params, "circuit", null);
        adapter.selectCircuit(circuit);
        return map("ok", true, "circuit", circuit);
      }
      case "show_view" -> {
        String view = str(params, "view", "appearance");
        adapter.showView(view);
        return map("view", view);
      }
      case "appearance_get" -> {
        return adapter.appearanceGet(str(params, "circuit", null));
      }
      case "appearance_apply" -> {
        Map<String, Object> spec = obj(params.get("spec"));
        return adapter.appearanceApply(spec);
      }
      case "appearance_reset" -> {
        return adapter.appearanceReset(
            str(params, "circuit", null), str(params, "mode", "default_custom"));
      }
      case "screenshot" -> {
        String out = str(params, "out", null);
        File file = out == null
            ? new File(System.getProperty("java.io.tmpdir"), "logisim-appearance.png")
            : new File(out);
        return adapter.screenshot(file, str(params, "kind", "canvas"));
      }
      case "save" -> {
        String target = str(params, "file", null);
        return adapter.save(target == null ? null : new File(target));
      }
      case "probe_libraries" -> {
        return adapter.probeLibraries();
      }
      case "probe_component" -> {
        String name = str(params, "name", null);
        if (name == null || name.isBlank()) {
          throw new BridgeException("E_BAD_PARAM", "缺少 name（元件名，如 Register）", "", null);
        }
        Object raw = params.get("attrs");
        Map<String, Object> attrs = raw instanceof Map ? Json.obj(raw) : Map.of();
        return adapter.probeComponent(name, str(params, "lib", null), attrs);
      }
      case "close" -> {
        Map<String, Object> out = map("closing", true);
        out.put("save", Json.b(params.get("save"), false));
        return out;
      }
      default -> throw new BridgeException(
          "E_UNKNOWN_CMD", "未知命令 " + cmd,
          "支持 ping/status/list_circuits/select_circuit/show_view/appearance_get/"
              + "appearance_apply/appearance_reset/screenshot/save/probe_libraries/"
              + "probe_component/close",
          null);
    }
  }

  private static Map<String, Object> obj(Object v) {
    if (v instanceof Map) return Json.obj(v);
    throw new BridgeException("E_BAD_PARAM", "缺少 spec 对象");
  }

  private static String str(Map<String, Object> m, String key, String def) {
    Object v = m == null ? null : m.get(key);
    return v == null ? def : String.valueOf(v);
  }

  private static Map<String, Object> map(Object... kv) {
    Map<String, Object> m = new LinkedHashMap<>();
    for (int i = 0; i + 1 < kv.length; i += 2) m.put(String.valueOf(kv[i]), kv[i + 1]);
    return m;
  }

  @SuppressWarnings("unused")
  private static List<Object> list(Object v) {
    return v instanceof List ? Json.arr(v) : List.of();
  }
}
