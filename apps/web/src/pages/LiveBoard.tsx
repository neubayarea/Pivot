import { Link } from "react-router-dom";
import Card from "../components/Card";
import Kicker from "../components/Kicker";
import Stamp from "../components/Stamp";

// S1 · Live board. Placeholder layout; C02 fills momentum, pivots and stats.
export default function LiveBoard() {
  return (
    <>
      <div className="headline">
        <Kicker>Latest pivot · 63′</Kicker>
        <span className="x">Substitution flipped the left flank</span>
      </div>
      <div className="grid1">
        <div className="stack">
          <Card title="Momentum" note="coming in C02">
            <div className="placeholder">Momentum chart</div>
          </Card>
          <div className="lower">
            <Card title="Why it turned" note="63′">
              <p className="muted">The verified explanation for the latest pivot appears here.</p>
            </Card>
            <Card title="Events" note="auto-scroll">
              <p className="muted">Live event feed.</p>
            </Card>
          </div>
        </div>
        <div className="stack">
          <Card title="Pivots" note="3 found">
            <Link to="/pivot/demo-63" className="pv-link">
              <span className="m">63′</span>
              <span>
                <b>Substitution flipped the left flank</b>
                <br />
                <Stamp tone="ok">Verified ✓</Stamp>
              </span>
            </Link>
          </Card>
          <Card title="Match stats">
            <p className="muted">Possession, shots, xG.</p>
          </Card>
        </div>
      </div>
    </>
  );
}
