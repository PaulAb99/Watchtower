import { useEffect, useMemo, useState } from "react";
import { cloudApi } from "./structural/cloudApi";
import { createPiApi } from "./structural/piApi";
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [page, setPage] = useState("dashboard");
  const [selectedSystem, setSelectedSystem] = useState(null);

  async function checkAuth() {
    try {
      const data = await cloudApi.me();
      setUser(data.user);
    } catch {
      setUser(null);
    } finally {
      setAuthChecked(true);
    }
  }

  useEffect(() => {
    checkAuth();
  }, []);

  if (!authChecked) {
    return (
      <main className="authPage">
        <section className="authCard">
          <h1>Watchtower</h1>
          <p>Loading...</p>
        </section>
      </main>
    );
  }

  if (!user) {
    return <AuthPage onAuth={checkAuth} />;
  }

  if (page === "system" && selectedSystem) {
    return (
      <SystemPage
        user={user}
        system={selectedSystem}
        onBack={() => {
          setSelectedSystem(null);
          setPage("dashboard");
        }}
        onLogout={async () => {
          await cloudApi.logout();
          setUser(null);
        }}
      />
    );
  }

  if (page === "events") {
    return (
      <EventsPage
        user={user}
        onBack={() => setPage("dashboard")}
        onLogout={async () => {
          await cloudApi.logout();
          setUser(null);
        }}
      />
    );
  }

  return (
    <DashboardPage
      user={user}
      onOpenSystem={(system) => {
        setSelectedSystem(system);
        setPage("system");
      }}
      onOpenEvents={() => setPage("events")}
      onLogout={async () => {
        await cloudApi.logout();
        setUser(null);
      }}
    />
  );
}

function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();

    try {
      setError("");

      if (mode === "register") {
        if (password !== confirmPassword) {
          setError("Passwords do not match");
          return;
        }

        await cloudApi.register(email, password);
      } else {
        await cloudApi.login(email, password);
      }

      await onAuth();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="authPage">
      <section className="authCard">
        <div className="authHeader">
          <h1>Watchtower</h1>
          <p>Raspberry Pi Surveillance Dashboard</p>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={submit} className="authForm">
          <label>
            Email
            <input
              type="email"
              value={email}
              placeholder="you@example.com"
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              placeholder="Minimum 8 characters"
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {mode === "register" && (
            <label>
              Confirm password
              <input
                type="password"
                value={confirmPassword}
                placeholder="Repeat password"
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
              />
            </label>
          )}

          <button type="submit">
            {mode === "login" ? "Login" : "Create account"}
          </button>
        </form>

        <button
          className="textButton"
          onClick={() => {
            setError("");
            setMode(mode === "login" ? "register" : "login");
          }}
        >
          {mode === "login"
            ? "New here? Create account"
            : "Already have an account? Login"}
        </button>

        <p className="muted smallText">
          An account is mandatory to access the dashboard.
        </p>
      </section>
    </main>
  );
}

function Topbar({ user, onLogout, children }) {
  return (
    <header className="topbar">
      <div>
        <h1>Watchtower</h1>
        <p>{children}</p>
      </div>

      <div className="topbarActions">
        <span className="muted">{user.email}</span>
        <button className="secondaryButton" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}

function DashboardPage({ user, onOpenSystem, onOpenEvents, onLogout }) {
  const [systems, setSystems] = useState([]);
  const [error, setError] = useState("");

  async function loadSystems() {
    try {
      const data = await cloudApi.getSystems();
      setSystems(data.systems);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadSystems();
  }, []);

  return (
    <main className="page">
      <Topbar user={user} onLogout={onLogout}>
        Surveillance Dashboard
      </Topbar>

      {error && <div className="error">{error}</div>}

      <div className="dashboardActions">
        <button onClick={onOpenEvents}>Open Event Tracker</button>
      </div>

      <section className="grid">
        {systems.map((system) => (
          <article className="card" key={system.id}>
            <h2>{system.name}</h2>
            <p>{system.location || "No location"}</p>
            <p className="muted">{system.api_base_url || "No Pi API URL set"}</p>

            <div className="systemMeta">
              <span className="badge online">Registered</span>
              <span>Status: {system.status}</span>
            </div>

            <button onClick={() => onOpenSystem(system)}>Open system</button>
          </article>
        ))}
      </section>
    </main>
  );
}

function SystemPage({ user, system, onBack, onLogout }) {
  const api = useMemo(() => {
    return createPiApi(system.api_base_url);
  }, [system.api_base_url]);

  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [step, setStep] = useState(2);
  const [error, setError] = useState("");

  async function refreshStatus() {
    try {
      const data = await api.getStatus();
      setStatus(data);
      setError("");
    } catch {
      setError("Could not connect to Pi API");
    }
  }

  async function refreshEvents() {
    try {
      const data = await cloudApi.getSystemEvents(system.id);
      setEvents(data.events);
    } catch (err) {
      console.error(err);
    }
  }

  async function run(action) {
    try {
      await action();
      await refreshStatus();
    } catch {
      setError("Command failed");
    }
  }

  useEffect(() => {
    refreshStatus();
    refreshEvents();

    const id = setInterval(() => {
      refreshStatus();
      refreshEvents();
    }, 3000);

    return () => clearInterval(id);
  }, [api, system.id]);

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <button className="secondaryButton" onClick={onBack}>
            ← Dashboard
          </button>
          <h1>{system.name}</h1>
          <p>{system.location}</p>
        </div>

        <div className="topbarActions">
          <span className={error ? "badge offline" : "badge online"}>
            {error ? "Offline" : "Online"}
          </span>
          <span className="muted">{user.email}</span>
          <button className="secondaryButton" onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="layout">
        <div className="mainColumn">
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
        </div>

        <aside className="sideColumn">
          <div className="card">
            <h2>Mode</h2>

            <div className="buttonStack">
              <button onClick={() => run(() => api.setManual())}>
                Manual Mode
              </button>

              <button onClick={() => run(() => api.setFollow())}>
                Follow Mode
              </button>
            </div>
          </div>

          <div className="card">
            <h2>Manual Controls</h2>

            <label>
              Step
              <input
                type="number"
                min="0.1"
                max="10"
                step="0.1"
                value={step}
                onChange={(event) => setStep(Number(event.target.value))}
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
          </div>
        </aside>
      </section>

      <section className="card systemEventsCard">
        <h2>Recent Events</h2>

        {events.length === 0 ? (
          <p className="muted">No events yet.</p>
        ) : (
          <div className="systemEventGrid">
            {events.slice(0, 8).map((event) => (
              <EventCard key={event.id} event={event} compact />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function EventsPage({ user, onBack, onLogout }) {
  const [systems, setSystems] = useState([]);
  const [selectedSystemId, setSelectedSystemId] = useState("");
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");

  async function loadSystems() {
    try {
      const data = await cloudApi.getSystems();
      setSystems(data.systems);

      if (data.systems.length > 0) {
        setSelectedSystemId(String(data.systems[0].id));
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadEvents(systemId) {
    if (!systemId) {
      return;
    }

    try {
      const data = await cloudApi.getSystemEvents(systemId);
      setEvents(data.events);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadSystems();
  }, []);

  useEffect(() => {
    loadEvents(selectedSystemId);
  }, [selectedSystemId]);

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <button className="secondaryButton" onClick={onBack}>
            ← Dashboard
          </button>
          <h1>Event Tracker</h1>
          <p>Review detections and optional snapshots.</p>
        </div>

        <div className="topbarActions">
          <span className="muted">{user.email}</span>
          <button className="secondaryButton" onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="card">
        <label>
          System
          <select
            value={selectedSystemId}
            onChange={(event) => setSelectedSystemId(event.target.value)}
          >
            {systems.map((system) => (
              <option key={system.id} value={system.id}>
                {system.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="eventGrid">
        {events.length === 0 ? (
          <div className="card">
            <p className="muted">No events found.</p>
          </div>
        ) : (
          events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))
        )}
      </section>
    </main>
  );
}

function EventCard({ event, compact = false }) {
  const [reviewed, setReviewed] = useState(Boolean(event.reviewed));

  async function markReviewed() {
    await cloudApi.markEventReviewed(event.id);
    setReviewed(true);
  }

  return (
    <article className="card eventCard">
      <div className="eventHeader">
        <div>
          <h3>{event.event_type}</h3>
          <p className="muted">{new Date(event.created_at).toLocaleString()}</p>
        </div>

        <span className={reviewed ? "badge online" : "badge offline"}>
          {reviewed ? "Reviewed" : "New"}
        </span>
      </div>

      <p>Label: {event.label || "-"}</p>
      <p>Confidence: {event.confidence ?? "-"}</p>
      <p>Track ID: {event.track_id ?? "-"}</p>

      {event.has_image && (
        <a
          className={compact ? "eventThumbSmall" : "eventThumb"}
          href={cloudApi.eventImageUrl(event.id)}
          target="_blank"
          rel="noreferrer"
        >
          <img src={cloudApi.eventImageUrl(event.id)} alt="Event snapshot" />
        </a>
      )}

      {!compact && !reviewed && (
        <button onClick={markReviewed}>Mark reviewed</button>
      )}
    </article>
  );
}

export default App;