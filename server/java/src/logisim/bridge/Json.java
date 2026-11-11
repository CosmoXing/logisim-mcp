package logisim.bridge;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 最小 JSON 解析/输出，避免给桥引入第三方依赖。 */
public final class Json {
  private Json() {}

  public static Object parse(String text) {
    Parser p = new Parser(text);
    Object v = p.value();
    p.ws();
    if (p.i < p.s.length()) throw new IllegalArgumentException("JSON 尾部有多余内容");
    return v;
  }

  @SuppressWarnings("unchecked")
  public static Map<String, Object> obj(Object v) {
    if (v instanceof Map) return (Map<String, Object>) v;
    throw new IllegalArgumentException("期望 JSON 对象");
  }

  @SuppressWarnings("unchecked")
  public static List<Object> arr(Object v) {
    if (v instanceof List) return (List<Object>) v;
    throw new IllegalArgumentException("期望 JSON 数组");
  }

  public static String str(Object v, String def) {
    return v == null ? def : String.valueOf(v);
  }

  public static int i(Object v, int def) {
    if (v instanceof Number) return ((Number) v).intValue();
    if (v instanceof String) {
      try {
        return Integer.parseInt((String) v);
      } catch (NumberFormatException ignored) {
      }
    }
    return def;
  }

  public static boolean b(Object v, boolean def) {
    if (v instanceof Boolean) return (Boolean) v;
    if (v instanceof String) return Boolean.parseBoolean((String) v);
    return def;
  }

  public static String write(Object o) {
    StringBuilder sb = new StringBuilder();
    write(o, sb);
    return sb.toString();
  }

  private static void write(Object o, StringBuilder sb) {
    if (o == null) {
      sb.append("null");
    } else if (o instanceof String) {
      quote((String) o, sb);
    } else if (o instanceof Boolean || o instanceof Number) {
      sb.append(o);
    } else if (o instanceof Map) {
      sb.append('{');
      boolean first = true;
      for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) {
        if (!first) sb.append(',');
        first = false;
        quote(String.valueOf(e.getKey()), sb);
        sb.append(':');
        write(e.getValue(), sb);
      }
      sb.append('}');
    } else if (o instanceof Iterable) {
      sb.append('[');
      boolean first = true;
      for (Object v : (Iterable<?>) o) {
        if (!first) sb.append(',');
        first = false;
        write(v, sb);
      }
      sb.append(']');
    } else if (o.getClass().isArray()) {
      sb.append('[');
      int n = java.lang.reflect.Array.getLength(o);
      for (int i = 0; i < n; i++) {
        if (i > 0) sb.append(',');
        write(java.lang.reflect.Array.get(o, i), sb);
      }
      sb.append(']');
    } else {
      quote(String.valueOf(o), sb);
    }
  }

  private static void quote(String s, StringBuilder sb) {
    sb.append('"');
    for (int i = 0; i < s.length(); i++) {
      char c = s.charAt(i);
      switch (c) {
        case '"' -> sb.append("\\\"");
        case '\\' -> sb.append("\\\\");
        case '\n' -> sb.append("\\n");
        case '\r' -> sb.append("\\r");
        case '\t' -> sb.append("\\t");
        case '\b' -> sb.append("\\b");
        case '\f' -> sb.append("\\f");
        default -> {
          if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
          else sb.append(c);
        }
      }
    }
    sb.append('"');
  }

  private static final class Parser {
    final String s;
    int i;

    Parser(String s) {
      this.s = s;
    }

    void ws() {
      while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++;
    }

    char peek() {
      if (i >= s.length()) throw new IllegalArgumentException("JSON 意外结束");
      return s.charAt(i);
    }

    void expect(char c) {
      ws();
      if (i >= s.length() || s.charAt(i) != c) {
        throw new IllegalArgumentException("JSON 位置 " + i + " 期望 " + c);
      }
      i++;
    }

    Object value() {
      ws();
      char c = peek();
      if (c == '{') return object();
      if (c == '[') return array();
      if (c == '"') return string();
      if (c == 't' && s.startsWith("true", i)) {
        i += 4;
        return Boolean.TRUE;
      }
      if (c == 'f' && s.startsWith("false", i)) {
        i += 5;
        return Boolean.FALSE;
      }
      if (c == 'n' && s.startsWith("null", i)) {
        i += 4;
        return null;
      }
      return number();
    }

    Map<String, Object> object() {
      expect('{');
      Map<String, Object> m = new LinkedHashMap<>();
      ws();
      if (peek() == '}') {
        i++;
        return m;
      }
      while (true) {
        ws();
        String k = string();
        expect(':');
        m.put(k, value());
        ws();
        char c = peek();
        if (c == ',') {
          i++;
          continue;
        }
        expect('}');
        return m;
      }
    }

    List<Object> array() {
      expect('[');
      List<Object> out = new ArrayList<>();
      ws();
      if (peek() == ']') {
        i++;
        return out;
      }
      while (true) {
        out.add(value());
        ws();
        char c = peek();
        if (c == ',') {
          i++;
          continue;
        }
        expect(']');
        return out;
      }
    }

    String string() {
      expect('"');
      StringBuilder sb = new StringBuilder();
      while (i < s.length()) {
        char c = s.charAt(i++);
        if (c == '"') return sb.toString();
        if (c != '\\') {
          sb.append(c);
          continue;
        }
        if (i >= s.length()) throw new IllegalArgumentException("JSON 字符串转义不完整");
        char e = s.charAt(i++);
        switch (e) {
          case '"' -> sb.append('"');
          case '\\' -> sb.append('\\');
          case '/' -> sb.append('/');
          case 'b' -> sb.append('\b');
          case 'f' -> sb.append('\f');
          case 'n' -> sb.append('\n');
          case 'r' -> sb.append('\r');
          case 't' -> sb.append('\t');
          case 'u' -> {
            if (i + 4 > s.length()) throw new IllegalArgumentException("JSON \\u 转义不完整");
            sb.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
            i += 4;
          }
          default -> throw new IllegalArgumentException("JSON 非法转义 \\" + e);
        }
      }
      throw new IllegalArgumentException("JSON 字符串未结束");
    }

    Object number() {
      int start = i;
      if (peek() == '-') i++;
      while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
      if (i < s.length() && s.charAt(i) == '.') {
        i++;
        while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
      }
      if (i < s.length() && (s.charAt(i) == 'e' || s.charAt(i) == 'E')) {
        i++;
        if (i < s.length() && (s.charAt(i) == '+' || s.charAt(i) == '-')) i++;
        while (i < s.length() && Character.isDigit(s.charAt(i))) i++;
      }
      String num = s.substring(start, i);
      if (num.isEmpty() || "-".equals(num)) throw new IllegalArgumentException("JSON 非法数字");
      try {
        if (num.indexOf('.') < 0 && num.indexOf('e') < 0 && num.indexOf('E') < 0) {
          return Long.parseLong(num);
        }
        return Double.parseDouble(num);
      } catch (NumberFormatException e) {
        throw new IllegalArgumentException("JSON 非法数字 " + num);
      }
    }
  }
}
