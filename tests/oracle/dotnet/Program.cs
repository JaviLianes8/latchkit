// Runs latch scenarios through System.Threading.CountdownEvent and prints what it observed.
// Input on stdin, one scenario per line: "<count> <op> <op> ...". Ops:
//   d<k>  Signal(k), print CurrentCount or E:<exception> (the state is then unchanged)
//   u<k>  TryAddCount(k), print T or F or E:<exception>
//   r     print CurrentCount
//   w     print Wait(0) as T or F
//   n     print Wait(-5) as T or F or E:<exception>
// A scenario whose constructor throws prints "E:<exception>" alone. After the
// scenarios one fixed probe prints parked waiters across signals.
using System.Text;

static string Run(Func<string> op)
{
    try { return op(); }
    catch (Exception e) { return "E:" + e.GetType().Name; }
}

static string Scenario(string[] parts)
{
    CountdownEvent ev;
    try { ev = new CountdownEvent(int.Parse(parts[0])); }
    catch (Exception e) { return "E:" + e.GetType().Name; }
    var output = new List<string>();
    foreach (var op in parts.Skip(1))
    {
        output.Add(op[0] switch
        {
            'd' => Run(() => { ev.Signal(int.Parse(op[1..])); return ev.CurrentCount.ToString(); }),
            'u' => Run(() => ev.TryAddCount(int.Parse(op[1..])) ? "T" : "F"),
            'r' => ev.CurrentCount.ToString(),
            'w' => ev.Wait(0) ? "T" : "F",
            'n' => Run(() => ev.Wait(-5) ? "T" : "F"),
            _ => throw new ArgumentException(op),
        });
    }
    return string.Join(" ", output);
}

static string Parked()
{
    var ev = new CountdownEvent(3);
    var waiters = Enumerable.Range(0, 4).Select(_ => new Thread(() => ev.Wait())).ToList();
    waiters.ForEach(t => t.Start());
    var deadline = DateTime.UtcNow.AddSeconds(60);
    while (waiters.Any(t => (t.ThreadState & ThreadState.WaitSleepJoin) == 0))
    {
        if (DateTime.UtcNow > deadline) throw new InvalidOperationException("guard");
        Thread.Sleep(1);
    }
    var output = new List<string>();
    for (var i = 0; i < 3; i++)
    {
        ev.Signal();
        if (i < 2) output.Add(waiters.Count(t => t.IsAlive).ToString());
    }
    output.Add(waiters.Count(t => t.Join(60_000)).ToString());
    return "parked " + string.Join(" ", output);
}

string? line;
var result = new StringBuilder();
while (!string.IsNullOrEmpty(line = Console.ReadLine()))
{
    result.Append(Scenario(line.Trim().Split(' '))).Append('\n');
}
result.Append(Parked()).Append('\n');
Console.Out.Write(result.ToString());
