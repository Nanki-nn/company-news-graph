type GraphNode = {
  id: string;
  label: string;
  type: string;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

type GraphViewProps = {
  graph: GraphData;
};

export function GraphView({ graph }: GraphViewProps) {
  return (
    <section className="graph-layout">
      <div className="graph-card">
        <h2>Graph Preview</h2>
        <p>This is a placeholder view until Cytoscape.js or Sigma.js is wired in.</p>
        <div className="graph-columns">
          <div>
            <h3>Nodes</h3>
            <ul className="token-list">
              {graph.nodes.map((node) => (
                <li key={node.id}>
                  <strong>{node.label}</strong>
                  <span>{node.type}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Edges</h3>
            <ul className="token-list">
              {graph.edges.map((edge) => (
                <li key={edge.id}>
                  <strong>{edge.label}</strong>
                  <span>
                    {edge.source} -> {edge.target}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
