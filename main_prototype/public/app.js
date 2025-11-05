const { useContext, useEffect, useMemo, useRef, useState } = React;
const { BrowserRouter, Routes, Route, NavLink, Navigate } = ReactRouterDOM;

function formatTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function TimeSeriesChart({ title, subtitle, labels, datasets }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !labels?.length) return undefined;
    const context = canvasRef.current.getContext("2d");
    const chart = new Chart(context, {
      type: "line",
      data: {
        labels,
        datasets: datasets.map((dataset) => ({
          tension: 0.35,
          borderWidth: 3,
          fill: false,
          pointRadius: 0,
          ...dataset,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { color: "#4b5563" },
            grid: { display: false },
          },
          y: {
            ticks: { color: "#4b5563" },
            grid: { color: "rgba(148, 163, 184, 0.2)" },
          },
        },
        plugins: {
          legend: {
            labels: { color: "#1f2937" },
          },
          tooltip: {
            mode: "index",
            intersect: false,
            callbacks: {
              label: (context) => {
                const suffix = context.dataset.label?.includes("Price")
                  ? " NOK/MWh"
                  : " MW";
                return `${context.dataset.label}: ${context.formattedValue}${suffix}`;
              },
            },
          },
        },
      },
    });
    return () => chart.destroy();
  }, [labels, datasets]);

  return (
    <div className="card" style={{ minHeight: "320px", display: "grid", gap: "0.5rem" }}>
      <div>
        <h3 className="section-title">{title}</h3>
        {subtitle ? <small>{subtitle}</small> : null}
      </div>
      <div style={{ position: "relative", minHeight: "250px" }}>
        <canvas ref={canvasRef} />
      </div>
    </div>
  );
}

function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Enter any username & password to continue");
      return;
    }
    setError(null);
    onLogin({ username });
  };

  return (
    <div className="login-page">
      <div className="card login-card">
        <h1>UMM + Water Values</h1>
        <p>
          This lightweight prototype lets you explore production metrics and UMM outage
          activity in a single place. Use any credentials to sign in.
        </p>
        <form onSubmit={handleSubmit}>
          <label>
            Username
            <input
              type="text"
              placeholder="jane.doe"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              placeholder="••••••"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? <small style={{ color: "#dc2626" }}>{error}</small> : null}
          <button type="submit" className="primary-button">
            Enter prototype
          </button>
        </form>
      </div>
    </div>
  );
}

function WaterValuesPage({ data, loading }) {
  if (loading) {
    return <div className="card">Loading water value data…</div>;
  }

  if (!data) {
    return <div className="card">No water value dataset is available.</div>;
  }

  const totals = useMemo(() => {
    const stats = data.stats || {};
    const productionFallback = data.plants.reduce(
      (acc, plant) => acc + (plant.latestProduction || 0),
      0
    );
    const averageFallback = data.plants.length
      ? data.plants.reduce((acc, plant) => acc + (plant.waterValue || 0), 0) /
        data.plants.length
      : 0;
    return {
      totalProduction: (typeof stats.totalProductionMw === "number"
        ? stats.totalProductionMw
        : productionFallback
      ).toFixed(0),
      averageWaterValue: (typeof stats.averageWaterValue === "number"
        ? stats.averageWaterValue
        : averageFallback
      ).toFixed(2),
    };
  }, [data]);

  const productionChart = useMemo(() => {
    if (!data?.plants?.length) {
      return null;
    }
    const labels = data.plants[0].productionSeries.timestamps.map((timestamp) =>
      new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    );
    const datasets = data.plants.map((plant, index) => {
      const palette = ["#2563eb", "#0ea5e9", "#f97316", "#22c55e", "#a855f7"];
      return {
        label: plant.name,
        data: plant.productionSeries.values,
        borderColor: palette[index % palette.length],
      };
    });
    return { labels, datasets };
  }, [data]);

  const priceChart = useMemo(() => {
    if (!data?.priceCurve?.timestamps?.length) {
      return null;
    }
    const labels = data.priceCurve.timestamps.map((timestamp) =>
      new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    );
    return {
      labels,
      datasets: [
        {
          label: "Day-ahead Price",
          data: data.priceCurve.dayAhead,
          borderColor: "#2563eb",
        },
        {
          label: "Intra-day Price",
          data: data.priceCurve.intraDay,
          borderColor: "#f97316",
        },
      ],
    };
  }, [data]);

  return (
    <div className="page-container">
      <div className="card hero-panel">
        <div>
          <p className="section-title" style={{ marginBottom: "0.6rem" }}>
            Latest production snapshot
          </p>
          <p className="hero-subtitle">
            Consolidated view of hydro plants with calculated water values and price curves.
            Figures refresh whenever we ingest new Statnett and ENTSO-E datasets.
          </p>
        </div>
        <div className="metrics-grid">
          <div className="metric-tile">
            <span className="metric-label">Total production</span>
            <span className="metric-value">{totals.totalProduction} MW</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Average water value</span>
            <span className="metric-value">
              {totals.averageWaterValue} {data.priceCurrency || "EUR/MWh"}
            </span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Data timestamp</span>
            <span className="metric-value">{formatTimestamp(data.generatedAt)}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="section-title">Plant overview</h2>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Plant</th>
                <th>Area</th>
                <th>Water value</th>
                <th>Latest production</th>
                <th>Interval bands</th>
                <th>Max installed</th>
              </tr>
            </thead>
            <tbody>
              {data.plants.map((plant) => (
                <tr key={plant.id}>
                  <td>
                    <strong>{plant.name}</strong>
                  </td>
                  <td>{plant.area}</td>
                  <td>
                    {plant.waterValue != null
                      ? `${plant.waterValue.toFixed(2)} ${data.priceCurrency || "EUR/MWh"}`
                      : "—"}
                  </td>
                  <td>{plant.latestProduction} MW</td>
                  <td>
                    {plant.productionIntervals?.length
                      ? plant.productionIntervals
                          .map(
                            (interval) =>
                              `${interval.range} → ${interval.waterValue.toFixed(2)}`
                          )
                          .join(", ")
                      : "—"}
                  </td>
                  <td>{plant.maxInstalled} MW</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="chart-grid">
        {productionChart ? (
          <TimeSeriesChart
            title="Production by plant"
            subtitle="Four recent dispatch intervals"
            labels={productionChart.labels}
            datasets={productionChart.datasets}
          />
        ) : null}
        {priceChart ? (
          <TimeSeriesChart
            title="Spot price curves"
            subtitle="Intraday vs. day-ahead pricing"
            labels={priceChart.labels}
            datasets={priceChart.datasets}
          />
        ) : null}
      </div>
    </div>
  );
}

function SummaryTiles({ summary }) {
  if (!summary) return null;
  const formatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
  return (
    <div className="metrics-grid">
      <div className="metric-tile" style={{ background: "rgba(16, 185, 129, 0.12)", color: "#047857" }}>
        <span className="metric-label">Active events</span>
        <span className="metric-value">{summary.activeMessages}</span>
      </div>
      <div className="metric-tile" style={{ background: "rgba(59, 130, 246, 0.12)", color: "#1d4ed8" }}>
        <span className="metric-label">Total notices</span>
        <span className="metric-value">{summary.totalMessages}</span>
      </div>
      <div className="metric-tile" style={{ background: "rgba(249, 115, 22, 0.12)", color: "#c2410c" }}>
        <span className="metric-label">Capacity at risk</span>
        <span className="metric-value">
          {formatter.format(summary.totalCapacityAffectedMw || 0)} MW
        </span>
      </div>
    </div>
  );
}

function UmmPage({ data, summary, loading }) {
  const [query, setQuery] = useState("");
  const [areaFilter, setAreaFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const areas = useMemo(() => {
    const values = new Set((summary?.areaTotals || []).map((item) => item.area));
    data.forEach((item) => values.add(item.area));
    return Array.from(values).sort();
  }, [data, summary]);

  const statuses = useMemo(() => {
    const values = new Set(
      (summary?.overview?.statusBreakdown || []).map((item) => item.status)
    );
    data.forEach((item) => values.add(item.status));
    return Array.from(values).sort();
  }, [data, summary]);

  const filtered = useMemo(() => {
    return data.filter((item) => {
      const matchesQuery = query
        ? [
            item.messageId,
            item.participant,
            item.powerSystemResource,
            item.message,
          ]
            .join(" ")
            .toLowerCase()
            .includes(query.toLowerCase())
        : true;
      const matchesArea = areaFilter === "all" ? true : item.area === areaFilter;
      const matchesStatus = statusFilter === "all" ? true : item.status === statusFilter;
      return matchesQuery && matchesArea && matchesStatus;
    });
  }, [data, query, areaFilter, statusFilter]);

  if (loading) {
    return <div className="card">Loading UMM feed…</div>;
  }

  return (
    <div className="page-container">
      <div className="card hero-panel">
        <div>
          <p className="section-title" style={{ marginBottom: "0.6rem" }}>
            Outage transparency feed
          </p>
          <p className="hero-subtitle">
            Filter recent unavailability messages by bidding area, operator, or status. The
            summary tiles mirror the existing dashboard experience.
          </p>
        </div>
        <SummaryTiles summary={summary?.overview} />
      </div>

      <div className="card">
        <div className="table-search">
          <input
            type="text"
            placeholder="Search by ID, participant or asset"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select
            className="filter-select"
            value={areaFilter}
            onChange={(event) => setAreaFilter(event.target.value)}
          >
            <option value="all">All areas</option>
            {areas.map((area) => (
              <option key={area} value={area}>
                {area}
              </option>
            ))}
          </select>
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
        <div className="table-wrapper" style={{ marginTop: "1.5rem" }}>
          <table>
            <thead>
              <tr>
                <th>Message ID</th>
                <th>Participant</th>
                <th>Asset</th>
                <th>Area</th>
                <th>Status</th>
                <th>Outage type</th>
                <th>Capacity</th>
                <th>Window</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length ? (
                filtered.map((item) => {
                  const statusClass = (item.status || "")
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, "-");
                  const outageClass = (item.outageType || "")
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, "-");
                  return (
                    <tr key={item.messageId}>
                      <td>{item.messageId}</td>
                      <td>{item.participant}</td>
                      <td>{item.powerSystemResource}</td>
                      <td>{item.area}</td>
                      <td>
                        <span className={`tag ${statusClass}`}>{item.status}</span>
                      </td>
                      <td>
                        <span className={`tag ${outageClass}`}>{item.outageType}</span>
                      </td>
                      <td>{item.capacityAffectedMw} MW</td>
                      <td>
                        <div>{formatTimestamp(item.eventStart)}</div>
                        <small>→ {formatTimestamp(item.eventEnd)}</small>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="8" className="empty-state">
                    No messages match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {summary?.areaTotals?.length ? (
        <div className="card">
          <h2 className="section-title">Recent outage totals by area</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Area</th>
                  <th>Messages</th>
                  <th>Capacity impacted</th>
                </tr>
              </thead>
              <tbody>
                {summary.areaTotals.map((row) => (
                  <tr key={row.area}>
                    <td>{row.area}</td>
                    <td>{row.issues}</td>
                    <td>{row.capacityMw} MW</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {summary?.largeOutages?.length ? (
        <div className="card">
          <h2 className="section-title">Large outage spotlight</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Area</th>
                  <th>Events ≥ 50 MW</th>
                  <th>Max capacity loss</th>
                </tr>
              </thead>
              <tbody>
                {summary.largeOutages.map((row) => (
                  <tr key={`${row.area}-${row.maxCapacityMw}`}>
                    <td>{row.area}</td>
                    <td>{row.events}</td>
                    <td>{row.maxCapacityMw} MW</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {summary?.overview?.outageTypeBreakdown?.length ? (
        <div className="card">
          <h2 className="section-title">Message mix</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Outage type</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {summary.overview.outageTypeBreakdown.map((row) => (
                  <tr key={row.outageType}>
                    <td>{row.outageType}</td>
                    <td>{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {summary.overview.statusBreakdown?.length ? (
            <div style={{ marginTop: "1rem" }}>
              <strong>Status breakdown</strong>
              <div style={{ display: "flex", gap: "12px", marginTop: "0.5rem", flexWrap: "wrap" }}>
                {summary.overview.statusBreakdown.map((item) => (
                  <span key={item.status} className="tag">
                    {item.status}: {item.count}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DashboardLayout({ user, onLogout }) {
  return (
    <div className="app-shell">
      <nav className="page-container top-nav">
        <div className="brand">
          <div className="brand-circle">UV</div>
          <div>
            <strong>Utility Vision</strong>
            <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>Hydro + UMM insights</div>
          </div>
        </div>
        <div className="nav-links">
          <NavLink className={({ isActive }) => (isActive ? "nav-button active" : "nav-button")} to="/water">
            Water values
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "nav-button active" : "nav-button")} to="/umms">
            UMM feed
          </NavLink>
          <button type="button" className="nav-button logout-button" onClick={onLogout}>
            Log out {user?.username ? `(${user.username})` : ""}
          </button>
        </div>
      </nav>
      <main style={{ flex: 1 }}>
        <Routes>
          <Route path="/water" element={<DashboardWaterRoute />} />
          <Route path="/umms" element={<DashboardUmmRoute />} />
          <Route path="*" element={<Navigate to="/water" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function DashboardWaterRoute() {
  const { waterData, waterLoading } = useContext(AppDataContext);
  return <WaterValuesPage data={waterData} loading={waterLoading} />;
}

function DashboardUmmRoute() {
  const { ummData, ummSummary, ummLoading } = useContext(AppDataContext);
  return <UmmPage data={ummData} summary={ummSummary} loading={ummLoading} />;
}

const AppDataContext = React.createContext({});

function App() {
  const [user, setUser] = useState(null);
  const [waterData, setWaterData] = useState(null);
  const [waterLoading, setWaterLoading] = useState(false);
  const [ummData, setUmmData] = useState([]);
  const [ummSummary, setUmmSummary] = useState(null);
  const [ummLoading, setUmmLoading] = useState(false);

  useEffect(() => {
    if (!user) return;

    const fetchWaterValues = async () => {
      setWaterLoading(true);
      try {
        const response = await fetch("/api/water-values");
        if (!response.ok) throw new Error("Failed to fetch water values");
        const payload = await response.json();
        setWaterData(payload);
      } catch (error) {
        console.error(error);
      } finally {
        setWaterLoading(false);
      }
    };

    const fetchUmms = async () => {
      setUmmLoading(true);
      try {
        const [messagesRes, summaryRes] = await Promise.all([
          fetch("/api/umms"),
          fetch("/api/umm/summary"),
        ]);
        if (!messagesRes.ok) throw new Error("Failed to fetch UMM messages");
        if (!summaryRes.ok) throw new Error("Failed to fetch UMM summary");
        const [messages, summary] = await Promise.all([
          messagesRes.json(),
          summaryRes.json(),
        ]);
        setUmmData(messages);
        setUmmSummary(summary);
      } catch (error) {
        console.error(error);
      } finally {
        setUmmLoading(false);
      }
    };

    fetchWaterValues();
    fetchUmms();
  }, [user]);

  const handleLogout = () => {
    setUser(null);
    setWaterData(null);
    setUmmData([]);
    setUmmSummary(null);
  };

  const contextValue = useMemo(
    () => ({ waterData, waterLoading, ummData, ummSummary, ummLoading }),
    [waterData, waterLoading, ummData, ummSummary, ummLoading]
  );

  return (
    <AppDataContext.Provider value={contextValue}>
      {!user ? (
        <LoginPage onLogin={setUser} />
      ) : (
        <BrowserRouter>
          <DashboardLayout user={user} onLogout={handleLogout} />
        </BrowserRouter>
      )}
    </AppDataContext.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
