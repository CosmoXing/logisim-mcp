package logisim.bridge;

import com.cburch.logisim.Main;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * 启动器：先开本地控制服务，再调用 Logisim 自己的 Main.main 打开 GUI。
 *
 * <p>用法： java -cp "logisim-bridge.jar;logisim-evolution-5.0.0-all.jar"
 * logisim.bridge.BridgeMain --portfile=&lt;json&gt; --log=&lt;log&gt; file.circ
 */
public final class BridgeMain {
  private BridgeMain() {}

  public static void main(String[] args) throws Exception {
    List<String> logisimArgs = new ArrayList<>();
    File portFile = null;
    File logFile = null;
    for (String arg : args) {
      if (arg.startsWith("--portfile=")) {
        portFile = new File(arg.substring("--portfile=".length()));
      } else if (arg.startsWith("--log=")) {
        logFile = new File(arg.substring("--log=".length()));
      } else {
        logisimArgs.add(arg);
      }
    }
    if (portFile == null) {
      System.err.println("缺少 --portfile=<path>");
      System.exit(2);
    }
    if (logFile == null) {
      logFile = new File(portFile.getAbsoluteFile().getParentFile(), "agent.log");
    }
    if (logFile.getParentFile() != null) logFile.getParentFile().mkdirs();
    if (portFile.getParentFile() != null) portFile.getParentFile().mkdirs();

    LogisimAdapter adapter = new LogisimAdapter();
    if (!logisimArgs.isEmpty()) {
      adapter.setRequestedFile(new File(logisimArgs.get(0)).getAbsoluteFile());
    }
    BridgeServer server = new BridgeServer(portFile, logFile, BridgeServer.newToken(), adapter);
    server.start();
    server.log("logisim 参数：" + logisimArgs);
    try {
      Main.main(logisimArgs.toArray(new String[0]));
    } catch (Throwable t) {
      server.log("Logisim 启动失败：" + t);
      t.printStackTrace();
      System.exit(1);
    }
    server.log("Logisim 主入口已返回，桥继续驻留");
    Thread.currentThread().join();
  }
}
