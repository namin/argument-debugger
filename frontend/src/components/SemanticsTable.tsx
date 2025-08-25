import React from "react";

export default function SemanticsTable({
  ids,
  id2atom,
  semantics,
}: {
  ids: string[];
  id2atom: Record<string, string>;
  semantics: {
    grounded: string[];
    preferred: string[][];
    stable: string[][];
    complete: string[][];
    stage: string[][];
    semi_stable: string[][];
  };
}) {
  const rows = ids.map((id) => {
    const a = id2atom[id];
    const inFam = (fam: any): string => {
      if (Array.isArray(fam) && fam.length && Array.isArray(fam[0])) {
        const k = fam.length;
        const m = (fam as string[][]).filter((S) => S.includes(a)).length;
        return `${m}/${k}`;
      }
      if (Array.isArray(fam)) {
        return (fam as string[]).includes(a) ? "✓" : "";
      }
      return "";
    };
    return {
      id,
      atom: a,
      grounded: inFam(semantics.grounded),
      preferred: inFam(semantics.preferred),
      stable: inFam(semantics.stable),
      complete: inFam(semantics.complete),
      stage: inFam(semantics.stage),
      semi: inFam(semantics.semi_stable),
    };
  });

  return (
    <div style={{ overflow: "auto" }}>
      <table className="grid">
        <thead>
          <tr>
            <th style={{ textAlign: "right" }}>ID</th>
            <th>Atom</th>
            <th>Grounded</th>
            <th>Pref</th>
            <th>Stable</th>
            <th>Complete</th>
            <th>Stage</th>
            <th>SemiSt</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td style={{ textAlign: "right" }}>{r.id}</td>
              <td>
                <code>{r.atom}</code>
              </td>
              <td className="center">{r.grounded}</td>
              <td className="center">{r.preferred}</td>
              <td className="center">{r.stable}</td>
              <td className="center">{r.complete}</td>
              <td className="center">{r.stage}</td>
              <td className="center">{r.semi}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
