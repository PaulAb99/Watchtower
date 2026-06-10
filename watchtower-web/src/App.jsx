import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useParams } from "react-router-dom";
import { systems } from "./structural/systems";
import { createPiApi } from "./structural/piApi";
import "./App.css";

function DashboardPage() {
  return (
    <main className="page">
      <header className="topbar">
        <h1>Watchtower</h1>
        <span>Surveillance Dashboard</span>
      </header>

      <section className="grid">
        {systems.map((system) => (
          <article className="card" key={system.id}>
            <h2>{system.name}</h2>
            <p>{system.location}</p>
            <p className="muted">{system.apiBaseUrl}</p>

            <Link className="buttonLink" to={`/systems/${system.id}`}>
              Open system
            </Link>
          </article>
        ))}
      </section>
    </main>
  );
}

function SystemPage() {
  const { systemId } = useParams();
  const system = systems.find((item) => item.id === systemId);

  const api = useMemo(() => {
    if (!system) {
      return null;
    }

    return createPiApi(system.apiBaseUrl);
  }, [system]);

  if (!system || !api) {
    return (
      <main className="page">
        <h1>System not found</h1>
        <Link to="/">Back</Link>
      </main>
    );
  }

  return <CameraSystemView system={system} api={api} />;
}

function CameraSystemView({ system, api }) {
  const [status, setStatus] = useState(null);
  const [step, setStep] = useState(2);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const data = await api.getStatus();
      setStatus(data);
      setError("");
    } catch (err) {
      console.error(err);
      setError("Could not connect to Pi API");
    }
  }

  async function run(action) {
    try {
      await action();
      await refresh();
    } catch (err) {
      console.error(err);
      setError("Command failed");
    }
  }

  useEffect(() => {
    refresh();

    const id = setInterval(refresh, 2000);

    return () => clearInterval(id);
  }, [api]);

  return (
  <main className="page">
    <section className="systemShell">
      <header className="topbar">
        <div>
          <Link to="/">← Dashboard</Link>
          <h1>{system.name}</h1>
          <p>{system.location}</p>
        </div>

        <span className={error ? "badge offline" : "badge online"}>
          {error ? "Offline" : "Online"}
        </span>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="dashboardLayout">
        <aside className="controlsPanel card">
          <h2>Mode</h2>

          <div className="buttonStack">
            <button onClick={() => run(() => api.setManual())}>
              Manual Mode
            </button>

            <button onClick={() => run(() => api.setFollow())}>
              Follow Mode
            </button>
          </div>

          <h2>Servo</h2>

          <label>
            Step
            <input
              type="number"
              min="0.1"
              max="10"
              step="0.1"
              value={step}
              onChange={(e) => setStep(Number(e.target.value))}
            />
          </label>

          <div className="dpad">
            <button className="up" onClick={() => run(() => api.moveUp(step))}>
              Up
            </button>

            <button className="left" onClick={() => run(() => api.moveLeft(step))}>
              Left
            </button>

            <button className="center" onClick={() => run(() => api.center())}>
              Center
            </button>

            <button className="right" onClick={() => run(() => api.moveRight(step))}>
              Right
            </button>

            <button className="down" onClick={() => run(() => api.moveDown(step))}>
              Down
            </button>
          </div>

          <div className="eventsBox">
            <h2>Recent Events</h2>
            <p className="muted">
              Unknown-person captures will appear here later.
            </p>
          </div>
        </aside>

        <section className="cameraPanel">
          <div className="card">
            <h2>Live Feed</h2>

            <div className="videoBox">
              <img src={api.videoFeedUrl()} alt="Camera feed" />
            </div>
          </div>

          <div className="card status">
            <h2>Status</h2>

            <div className="statsGrid">
              <p>Mode: {status?.mode ?? "-"}</p>
              <p>Pan: {status?.pan ?? "-"}</p>
              <p>Tilt: {status?.tilt ?? "-"}</p>
              <p>Tracked ID: {status?.tracked_id ?? "-"}</p>
              <p>
                Target:{" "}
                {status?.target_x != null && status?.target_y != null
                  ? `${status.target_x}, ${status.target_y}`
                  : "-"}
              </p>
            </div>
          </div>
        </section>
      </section>
    </section>
  </main>
);
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/systems/:systemId" element={<SystemPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;