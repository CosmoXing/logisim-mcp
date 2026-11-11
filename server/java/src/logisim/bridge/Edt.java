package logisim.bridge;

import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import javax.swing.SwingUtilities;

/** 统一把模型操作切到 EDT，并带超时，避免 invokeAndWait 死锁。 */
public final class Edt {
  private Edt() {}

  public static <T> T run(Callable<T> task, long timeoutMs) {
    if (SwingUtilities.isEventDispatchThread()) {
      try {
        return task.call();
      } catch (BridgeException be) {
        throw be;
      } catch (Exception e) {
        throw new BridgeException("E_INTERNAL", "EDT 任务失败：" + e.getMessage(), e);
      }
    }
    FutureTask<T> future = new FutureTask<>(task);
    SwingUtilities.invokeLater(future);
    try {
      return future.get(timeoutMs, TimeUnit.MILLISECONDS);
    } catch (TimeoutException e) {
      future.cancel(false);
      throw new BridgeException(
          "E_EDT_TIMEOUT", "等待 Logisim 界面响应超时（" + timeoutMs + "ms）",
          "界面可能被模态对话框挡住，请检查 Logisim 窗口", null);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new BridgeException("E_INTERNAL", "等待 EDT 时被中断", e);
    } catch (ExecutionException e) {
      Throwable cause = e.getCause();
      if (cause instanceof BridgeException be) throw be;
      throw new BridgeException("E_INTERNAL", "EDT 任务异常：" + cause, cause);
    }
  }
}
