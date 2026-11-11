package logisim.bridge;

import java.util.LinkedHashMap;
import java.util.Map;

/** 带错误码的桥异常，直接映射成协议里的 error 对象。 */
public class BridgeException extends RuntimeException {
  public final String code;
  public final String hint;
  public final Map<String, Object> detail;

  public BridgeException(String code, String message) {
    this(code, message, null, null, null);
  }

  public BridgeException(String code, String message, Throwable cause) {
    this(code, message, null, null, cause);
  }

  public BridgeException(String code, String message, String hint, Map<String, Object> detail) {
    this(code, message, hint, detail, null);
  }

  public BridgeException(
      String code, String message, String hint, Map<String, Object> detail, Throwable cause) {
    super(message, cause);
    this.code = code;
    this.hint = hint;
    this.detail = detail == null ? new LinkedHashMap<>() : detail;
  }

  public Map<String, Object> toJson() {
    Map<String, Object> m = new LinkedHashMap<>();
    m.put("code", code);
    m.put("message", getMessage());
    if (hint != null && !hint.isBlank()) m.put("hint", hint);
    if (!detail.isEmpty()) m.put("detail", detail);
    return m;
  }
}
