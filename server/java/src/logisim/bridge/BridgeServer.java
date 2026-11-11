package logisim.bridge;

import com.cburch.logisim.proj.Projects;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/** 127.0.0.1 上的 NDJSON 控制服务；一次处理一行，命令串行。 */
public final class BridgeServer {
  private static final int MAX_LINE = 8 * 1024 * 1024;
  private final File portFile;
  private final File logFile;
  private final String token;
  private final LogisimAdapter adapter;
  private final Commands commands;
  private final AtomicBoolean closing = new AtomicBoolean(false);
  private ServerSocket server;
  private int port;

  public BridgeServer(File portFile, File logFile, String token, LogisimAdapter adapter) {
    this.portFile = portFile;
    this.logFile = logFile;
    this.token = token;
    this.adapter = adapter;
    this.commands = new Commands(adapter);
  }

  public void start() throws Exception {
    server = new ServerSocket(0, 50, InetAddress.getLoopbackAddress());
    port = server.getLocalPort();
    writeState("starting");
    Thread accept = new Thread(this::acceptLoop, "logisim-bridge-accept");
    accept.setDaemon(true);
    accept.start();
    Thread ready = new Thread(this::watchReady, "logisim-bridge-ready");
    ready.setDaemon(true);
    ready.start();
    log("服务已启动 127.0.0.1:" + port);
  }

  public int port() {
    return port;
  }

  private void acceptLoop() {
    while (!closing.get()) {
      try {
        Socket socket = server.accept();
        Thread t = new Thread(() -> serve(socket), "logisim-bridge-client");
        t.setDaemon(true);
        t.start();
      } catch (Exception e) {
        if (!closing.get()) log("accept 失败：" + e);
      }
    }
  }

  private void serve(Socket socket) {
    try (socket;
        BufferedReader in =
            new BufferedReader(
                new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
        BufferedWriter out =
            new BufferedWriter(
                new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8))) {
      String line;
      while ((line = in.readLine()) != null) {
        if (line.length() > MAX_LINE) {
          write(out, error(null, new BridgeException("E_LINE_TOO_LONG", "请求行过长")));
          break;
        }
        if (line.isBlank()) continue;
        Map<String, Object> response = handleLine(line);
        boolean isClose = "close".equals(response.remove("_cmd"));
        write(out, response);
        if (isClose) {
          new Thread(
                  () -> {
                    sleep(300);
                    adapter.dispose();
                    System.exit(0);
                  },
                  "logisim-bridge-exit")
              .start();
          break;
        }
      }
    } catch (Exception e) {
      log("客户端连接异常：" + e);
    }
  }

  private Map<String, Object> handleLine(String line) {
    Object id = null;
    try {
      Map<String, Object> req = Json.obj(Json.parse(line));
      id = req.get("id");
      Object tokenValue = req.get("token");
      if (tokenValue == null || !token.equals(String.valueOf(tokenValue))) {
        throw new BridgeException("E_AUTH", "token 不匹配");
      }
      String cmd = Json.str(req.get("cmd"), "");
      Object paramsValue = req.get("params");
      Map<String, Object> params = paramsValue instanceof Map ? Json.obj(paramsValue) : Map.of();
      long started = System.nanoTime();
      Map<String, Object> result = commands.handle(cmd, params);
      Map<String, Object> resp = new LinkedHashMap<>();
      resp.put("v", 1);
      resp.put("id", id);
      resp.put("ok", true);
      resp.put("result", result);
      resp.put("elapsed_ms", (System.nanoTime() - started) / 1_000_000);
      if ("close".equals(cmd)) resp.put("_cmd", "close");
      return resp;
    } catch (BridgeException be) {
      return error(id, be);
    } catch (Exception e) {
      log("命令异常：" + e);
      return error(id, new BridgeException("E_INTERNAL", "内部错误：" + e.getMessage(), e));
    }
  }

  private static Map<String, Object> error(Object id, BridgeException e) {
    Map<String, Object> resp = new LinkedHashMap<>();
    resp.put("v", 1);
    resp.put("id", id);
    resp.put("ok", false);
    resp.put("error", e.toJson());
    return resp;
  }

  private static void write(BufferedWriter out, Map<String, Object> msg) throws Exception {
    out.write(Json.write(msg));
    out.write("\n");
    out.flush();
  }

  private void watchReady() {
    long end = System.currentTimeMillis() + 90000;
    while (System.currentTimeMillis() < end && !closing.get()) {
      try {
        if (!Projects.getOpenProjects().isEmpty()) {
          writeState("ready");
          return;
        }
        Thread.sleep(300);
      } catch (InterruptedException e) {
        return;
      }
    }
  }

  private void writeState(String state) {
    Map<String, Object> m = new LinkedHashMap<>();
    m.put("protocol", 1);
    m.put("state", state);
    m.put("port", port);
    m.put("token", token);
    m.put("pid", ProcessHandle.current().pid());
    m.put("started", Instant.now().toString());
    try {
      Path target = portFile.toPath().toAbsolutePath();
      Path tmp = target.resolveSibling(target.getFileName() + ".tmp");
      Files.writeString(tmp, Json.write(m), StandardCharsets.UTF_8);
      try {
        Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING,
            StandardCopyOption.ATOMIC_MOVE);
      } catch (Exception e) {
        Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING);
      }
    } catch (Exception e) {
      log("写端口文件失败：" + e);
    }
  }

  public void log(String message) {
    String line = "[" + Instant.now() + "] " + message + System.lineSeparator();
    try (FileOutputStream fos = new FileOutputStream(logFile, true)) {
      fos.write(line.getBytes(StandardCharsets.UTF_8));
    } catch (Exception ignored) {
    }
  }

  public static String newToken() {
    byte[] bytes = new byte[32];
    new SecureRandom().nextBytes(bytes);
    StringBuilder sb = new StringBuilder();
    for (byte b : bytes) sb.append(String.format("%02x", b));
    return sb.toString();
  }

  private static void sleep(long ms) {
    try {
      Thread.sleep(ms);
    } catch (InterruptedException ignored) {
      Thread.currentThread().interrupt();
    }
  }
}
