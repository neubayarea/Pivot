import { Link, useParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import Kicker from "../components/Kicker";

// S2 · Pivot detail. Placeholder layout; C03 fills before/after and evidence.
export default function PivotDetail() {
  const { id = "" } = useParams();

  return (
    <>
      <div className="back">
        <Link to="/">← Live board</Link>
      </div>
      <div className="headline">
        <Kicker>Pivot · {id}</Kicker>
        <span className="x">Substitution flipped the left flank</span>
        <span className="sp" />
        <Link to={`/trace/${id}`} className="btn">
          Agent trace
        </Link>
        <Link to={`/whatif/${id}`} className="btn pri">
          What if…
        </Link>
      </div>
      <div className="grid2">
        <Card title="Pitch replay" note="coming in C03">
          <div className="placeholder">Pitch and scrubber</div>
        </Card>
        <div className="stack">
          <Card title="Before / after">
            <p className="muted">Ten minutes either side of the pivot.</p>
          </Card>
          <Card title="Why it turned">
            <p className="muted">Explanation with evidence chips.</p>
            <div>
              <Button variant="ghost">Not a turning point</Button>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
