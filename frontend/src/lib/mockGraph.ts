export function mockGraph(companyName: string) {
  return {
    nodes: [
      { id: "company:1", label: companyName || "Target Company", type: "Company" },
      { id: "event:1", label: "Product Launch", type: "Event" },
      { id: "event:2", label: "Partnership", type: "Event" },
      { id: "product:1", label: "AI Platform X", type: "Product" },
      { id: "partner:1", label: "PartnerCo", type: "Company" },
      { id: "source:1", label: "Press Release", type: "Source" },
      { id: "source:2", label: "Industry News", type: "Source" }
    ],
    edges: [
      { id: "edge:1", source: "company:1", target: "event:1", label: "INVOLVED_IN" },
      { id: "edge:2", source: "event:1", target: "product:1", label: "LAUNCHED" },
      { id: "edge:3", source: "company:1", target: "event:2", label: "INVOLVED_IN" },
      { id: "edge:4", source: "event:2", target: "partner:1", label: "PARTNERED_WITH" },
      { id: "edge:5", source: "event:1", target: "source:1", label: "REPORTED_BY" },
      { id: "edge:6", source: "event:2", target: "source:2", label: "REPORTED_BY" }
    ]
  };
}
