import { useState } from "react";

import { GraphView } from "../components/GraphView";
import { SummaryPanel } from "../components/SummaryPanel";
import { mockGraph } from "../lib/mockGraph";

export function App() {
  const [companyName, setCompanyName] = useState("Tesla");

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Company Event Graph</p>
          <h1>Track recent company dynamics as a graph.</h1>
          <p className="subcopy">
            Input a company name and time range, fetch news and disclosures,
            extract events, and visualize relationships with source evidence.
          </p>
        </div>
        <div className="query-card">
          <label>
            Company
            <input
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              placeholder="Tesla"
            />
          </label>
          <label>
            Time Range
            <input value="2026-03-01 to 2026-04-11" readOnly />
          </label>
          <button type="button">Run Research</button>
        </div>
      </section>

      <SummaryPanel companyName={companyName} />
      <GraphView graph={mockGraph(companyName)} />
    </main>
  );
}
