import React, { useEffect, useState } from "react";
import Workspace from "./components/Workspace";
import "./styles.css";

export default function App() {
  const [text, setText] = useState<string>("");

  // Persist editor content locally so you don't lose it on refresh
  useEffect(() => {
    const saved = localStorage.getItem("argdebugger:text");
    if (saved) setText(saved);
  }, []);
  useEffect(() => {
    localStorage.setItem("argdebugger:text", text || "");
  }, [text]);

  return (
    <div className="app">
      <header className="appbar">
        <div className="brand">Argument Debugger</div>
        <div className="spacer" />
        <a
          className="link"
          href="https://github.com/namin/argument-debugger"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </header>

      <main className="main">
        <Workspace text={text} onTextChange={setText} />
      </main>
    </div>
  );
}
