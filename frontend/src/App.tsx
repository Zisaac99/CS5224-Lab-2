import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, Health, Job, Summary, TopRow, UserStat } from "./api";

const DEFAULT_IDS = "214328887, 107830991";
const TERMINAL = new Set(["SUCCESS", "FAILED", "CANCELLED"]);
const fmt = (n: number | undefined) => (n ?? 0).toLocaleString("en-US");

function parseIds(raw: string): string[] {
  return raw.split(/[\s,]+/).filter(Boolean);
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [top, setTop] = useState<{ followers: TopRow[]; followees: TopRow[] } | null>(null);

  const [query, setQuery] = useState(DEFAULT_IDS);
  const [stats, setStats] = useState<UserStat[] | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [querying, setQuerying] = useState(false);

  const [job, setJob] = useState<Job | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobError, setJobError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const poll = useRef<number | null>(null);

  const runQuery = useCallback(async (raw: string) => {
    const ids = parseIds(raw);
    if (!ids.length) return setQueryError("ENTER AT LEAST ONE USER ID");
    if (ids.some((i) => !/^\d+$/.test(i))) return setQueryError("USER IDS MUST BE NUMERIC");
    setQuerying(true);
    setQueryError(null);
    try {
      setStats((await api.users(ids)).users);
    } catch (e) {
      setStats(null);
      setQueryError((e as Error).message.toUpperCase());
    } finally {
      setQuerying(false);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth(h);
      setOnline(true);
      api.jobs().then((r) => setJobs(r.jobs)).catch(() => setJobs([]));
      if (!h.results_run_id) return;
      const [s, f, g] = await Promise.all([api.summary(), api.top("followers"), api.top("followees")]);
      setSummary(s);
      setTop({ followers: f.users, followees: g.users });
      runQuery(query);
    } catch {
      setOnline(false);
    }
    // query intentionally excluded: refresh uses whatever is in the box at the time
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runQuery]);

  useEffect(() => {
    refreshAll();
    return () => {
      if (poll.current) window.clearInterval(poll.current);
    };
  }, [refreshAll]);

  const watchJob = (id: string) => {
    if (poll.current) window.clearInterval(poll.current);
    poll.current = window.setInterval(async () => {
      try {
        const j = await api.job(id);
        setJob(j);
        if (TERMINAL.has(j.state)) {
          window.clearInterval(poll.current!);
          poll.current = null;
          refreshAll();
        }
      } catch (e) {
        setJobError((e as Error).message.toUpperCase());
      }
    }, 5000);
  };

  const startJob = async () => {
    setSubmitting(true);
    setJobError(null);
    try {
      const j = await api.startJob();
      setJob({ ...j, state: "SUBMITTED" });
      watchJob(j.job_run_id);
    } catch (e) {
      setJobError((e as Error).message.toUpperCase());
    } finally {
      setSubmitting(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    runQuery(query);
  };

  const jobActive = !!job && !TERMINAL.has(job.state);

  return (
    <div className="shell">
      <header className="topbar">
        <span>[ CS5224 / LAB 02 ]</span>
        <span className="hide-sm">UNIT / AMAZON EMR</span>
        <span className="hide-sm">REV 2.0</span>
        <span className="status">
          <i className={online ? "led led-on" : online === false ? "led led-off" : "led"} />
          {online === null ? "LINK ..." : online ? "BACKEND ONLINE" : "BACKEND OFFLINE"}
        </span>
      </header>

      <section className="hero">
        <h1>
          FOLLOW
          <br />
          GRAPH<span className="accent">®</span>
        </h1>
        <div className="hero-meta">
          <p>TWITTER EGO-NETWORK // FOLLOWER + FOLLOWEE TELEMETRY</p>
          <p>
            SPARK ON AMAZON EMR &gt;&gt;&gt; S3 &gt;&gt;&gt; FASTAPI &gt;&gt;&gt; THIS TERMINAL
          </p>
          <dl className="hero-dl">
            <div>
              <dt>RESULT SET</dt>
              <dd>{health?.results_run_id ?? "NONE"}</dd>
            </div>
            <div>
              <dt>USERS INDEXED</dt>
              <dd>{fmt(health?.users_loaded)}</dd>
            </div>
          </dl>
        </div>
      </section>

      <main className="grid">
        {/* QUERY + CONSOLE */}
        <section className="cell span-4">
          <h2 className="label">[ 01 / QUERY ]</h2>
          <form className="query" onSubmit={onSubmit}>
            <label htmlFor="ids" className="sr-only">
              User IDs
            </label>
            <span className="prompt">&gt;</span>
            <input
              id="ids"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="USER IDS, COMMA SEPARATED"
              spellCheck={false}
              autoComplete="off"
            />
            <button type="submit" disabled={querying || !health?.results_run_id}>
              {querying ? "RUNNING..." : "EXECUTE >>>"}
            </button>
          </form>

          <h2 className="label">[ 02 / OUTPUT ]</h2>
          <output className="console" aria-live="polite">
            {queryError && <div className="err">!! {queryError}</div>}
            {!queryError && online === false && <div className="err">!! BACKEND UNREACHABLE</div>}
            {!queryError && online && !health?.results_run_id && (
              <div className="dim">// NO RESULTS LOADED. RUN THE PIPELINE IN PANEL 04.</div>
            )}
            {stats?.map((u) =>
              u.found ? (
                <div key={u.user_id}>
                  <samp>
                    {u.user_id} has {u.followers} followers
                  </samp>
                  <samp>
                    {u.user_id} has {u.followees} followees
                  </samp>
                </div>
              ) : (
                <div key={u.user_id} className="err">
                  !! {u.user_id} NOT FOUND IN DATASET
                </div>
              ),
            )}
            <span className="cursor" aria-hidden />
          </output>
        </section>

        {/* PER-USER READOUT */}
        <section className="cell span-2">
          <h2 className="label">[ 03 / READOUT ]</h2>
          {stats?.filter((u) => u.found).length ? (
            <div className="readouts">
              {stats
                .filter((u) => u.found)
                .map((u) => (
                  <article key={u.user_id} className="readout">
                    <div className="readout-id">UID / {u.user_id}</div>
                    <div className="readout-row">
                      <data value={u.followers}>{fmt(u.followers)}</data>
                      <span>FOLLOWERS</span>
                    </div>
                    <div className="readout-row">
                      <data value={u.followees}>{fmt(u.followees)}</data>
                      <span>FOLLOWEES</span>
                    </div>
                  </article>
                ))}
            </div>
          ) : (
            <p className="dim">// AWAITING QUERY</p>
          )}
        </section>

        {/* PIPELINE */}
        <section className="cell span-3">
          <h2 className="label">[ 04 / PIPELINE ]</h2>
          <button className="run" onClick={startJob} disabled={submitting || jobActive || !online}>
            {submitting ? "SUBMITTING..." : jobActive ? "JOB IN FLIGHT" : "RUN ANALYSIS ON EMR"}
          </button>
          {jobError && <p className="err">!! {jobError}</p>}
          {job && (
            <dl className="kv">
              <dt>JOB RUN</dt>
              <dd>{job.job_run_id}</dd>
              <dt>STATE</dt>
              <dd className={job.state === "SUCCESS" ? "ok" : job.state === "FAILED" ? "err" : ""}>
                {job.state}
                {jobActive && <span className="blink"> _</span>}
              </dd>
              {job.updated_at && (
                <>
                  <dt>UPDATED</dt>
                  <dd>{new Date(job.updated_at).toLocaleTimeString()}</dd>
                </>
              )}
              {job.state_details && (
                <>
                  <dt>DETAIL</dt>
                  <dd>{job.state_details}</dd>
                </>
              )}
            </dl>
          )}
          {jobs.length > 0 && (
            <>
              <h3 className="sublabel">/// RECENT RUNS</h3>
              <ul className="runs">
                {jobs.map((j) => (
                  <li key={j.job_run_id}>
                    <span>{j.job_run_id.slice(0, 12)}</span>
                    <span className={j.state === "SUCCESS" ? "" : j.state === "FAILED" ? "err" : "dim"}>
                      {j.state}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        {/* SUMMARY */}
        <section className="cell span-3">
          <h2 className="label">[ 05 / DATASET ]</h2>
          {summary ? (
            <dl className="kv">
              <dt>RAW LINES</dt>
              <dd>{fmt(summary.raw_lines)}</dd>
              <dt>MALFORMED</dt>
              <dd>{fmt(summary.malformed_lines)}</dd>
              <dt>SELF-LOOPS</dt>
              <dd>{fmt(summary.self_loop_lines)}</dd>
              <dt>DUPLICATES</dt>
              <dd className="accent">−{fmt(summary.duplicate_lines_removed)}</dd>
              <dt>UNIQUE EDGES</dt>
              <dd>{fmt(summary.unique_edges)}</dd>
              <dt>USERS</dt>
              <dd>{fmt(summary.users)}</dd>
            </dl>
          ) : (
            <p className="dim">// NO SUMMARY</p>
          )}
        </section>

        {/* LEADERBOARDS */}
        {(["followers", "followees"] as const).map((k, i) => (
          <section className="cell span-3" key={k}>
            <h2 className="label">
              [ 0{6 + i} / TOP {k.toUpperCase()} ]
            </h2>
            {top ? (
              <table className="board">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>USER ID</th>
                    <th>{k === "followers" ? "FLWR" : "FLWE"}</th>
                  </tr>
                </thead>
                <tbody>
                  {top[k].map((r, n) => (
                    <tr key={r.user_id} onClick={() => setQuery(r.user_id)} title="Load into query">
                      <td>{String(n + 1).padStart(2, "0")}</td>
                      <td>{r.user_id}</td>
                      <td>{fmt(r[k])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="dim">// NO DATA</p>
            )}
          </section>
        ))}
      </main>

      <div className="stripes" aria-hidden />
      <footer className="foot">
        <span>© CS5224 CLOUD COMPUTING</span>
        <span>SOURCE: SNAP EGO-TWITTER</span>
        <span>A FOLLOWS B ⇒ B +1 FOLLOWER / A +1 FOLLOWEE</span>
      </footer>
    </div>
  );
}
