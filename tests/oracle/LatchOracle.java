// Runs latch scenarios through java.util.concurrent and prints what it observed.
// Input on stdin, one scenario per line: "<count> <op> <op> ...". Ops:
//   d<k>  countDown() k times, print getCount()
//   r     print getCount()
//   w     print await(0 ms) as T or F
//   n     print await(-5 ms) as T or F
// A scenario whose constructor throws prints "E:<exception>" alone.
// After the scenarios, three fixed probes print one line each: parked waiters across
// count downs, a broken CyclicBarrier, and a terminated Phaser.
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.BrokenBarrierException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.Phaser;
import java.util.concurrent.TimeUnit;

public class LatchOracle {
    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String line;
        while ((line = in.readLine()) != null && !line.isEmpty()) {
            System.out.println(scenario(line.trim().split(" ")));
        }
        System.out.println(parked());
        System.out.println(barrier());
        System.out.println(phaser());
    }

    static String scenario(String[] parts) throws InterruptedException {
        CountDownLatch latch;
        try {
            latch = new CountDownLatch(Integer.parseInt(parts[0]));
        } catch (IllegalArgumentException e) {
            return "E:" + e.getClass().getSimpleName();
        }
        List<String> out = new ArrayList<>();
        for (int i = 1; i < parts.length; i++) {
            String op = parts[i];
            switch (op.charAt(0)) {
                case 'd' -> {
                    int k = Integer.parseInt(op.substring(1));
                    for (int j = 0; j < k; j++) latch.countDown();
                    out.add(Long.toString(latch.getCount()));
                }
                case 'r' -> out.add(Long.toString(latch.getCount()));
                case 'w' -> out.add(latch.await(0, TimeUnit.MILLISECONDS) ? "T" : "F");
                case 'n' -> out.add(latch.await(-5, TimeUnit.MILLISECONDS) ? "T" : "F");
                default -> throw new IllegalArgumentException(op);
            }
        }
        return String.join(" ", out);
    }

    static void untilWaiting(Thread t) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60);
        while (t.getState() != Thread.State.WAITING) {
            if (System.nanoTime() > deadline) throw new IllegalStateException("guard");
            Thread.sleep(1);
        }
    }

    static String parked() throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(3);
        List<Thread> waiters = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            Thread t = new Thread(() -> {
                try { latch.await(); } catch (InterruptedException e) { throw new RuntimeException(e); }
            });
            t.start();
            waiters.add(t);
        }
        for (Thread t : waiters) untilWaiting(t);
        List<String> out = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            latch.countDown();
            if (i < 2) {
                int still = 0;
                for (Thread t : waiters) if (t.getState() == Thread.State.WAITING) still++;
                out.add(Integer.toString(still));
            }
        }
        int done = 0;
        for (Thread t : waiters) { t.join(60_000); if (!t.isAlive()) done++; }
        out.add(Integer.toString(done));
        return "parked " + String.join(" ", out);
    }

    static String barrier() throws Exception {
        CyclicBarrier barrier = new CyclicBarrier(2);
        String[] seen = new String[1];
        Thread t = new Thread(() -> {
            try { barrier.await(); seen[0] = "returned"; }
            catch (BrokenBarrierException e) { seen[0] = "broken"; }
            catch (InterruptedException e) { seen[0] = "interrupted"; }
        });
        t.start();
        untilWaiting(t);
        t.interrupt();
        t.join(60_000);
        String later;
        try { barrier.await(0, TimeUnit.MILLISECONDS); later = "returned"; }
        catch (BrokenBarrierException e) { later = "broken"; }
        catch (java.util.concurrent.TimeoutException e) { later = "timeout"; }
        return "barrier " + seen[0] + " " + barrier.isBroken() + " " + later;
    }

    static String phaser() throws Exception {
        Phaser phaser = new Phaser(2);
        int[] seen = new int[1];
        Thread t = new Thread(() -> seen[0] = phaser.arriveAndAwaitAdvance());
        t.start();
        untilWaiting(t);
        phaser.forceTermination();
        t.join(60_000);
        int later = phaser.awaitAdvance(0);
        int arrive = phaser.arrive();
        return "phaser " + (seen[0] < 0) + " " + phaser.isTerminated() + " " + (later < 0)
            + " " + (arrive < 0);
    }
}
