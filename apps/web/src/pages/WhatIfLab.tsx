import { Link, useParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import Kicker from "../components/Kicker";

// S3 · What-if lab. Placeholder layout; scenario form and results come later.
export default function WhatIfLab() {
  const { id = "" } = useParams();

  return (
    <>
      <div className="back">
        <Link to={`/pivot/${id}`}>← Pivot {id}</Link>
      </div>
      <div className="headline">
        <Kicker>What-if lab</Kicker>
        <span className="x">What if the change never happened?</span>
      </div>
      <div className="grid3">
        <Card title="Scenario">
          <p className="muted">Pick a scenario or ask a question.</p>
          <div>
            <Button variant="primary">Run simulation</Button>
          </div>
        </Card>
        <Card title="Outcome" note="placeholder">
          <div className="placeholder">Win / draw / loss distribution</div>
        </Card>
      </div>
    </>
  );
}
