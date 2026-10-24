import { Link } from "react-router-dom";
import Card from "../components/Card";

export default function NotFound() {
  return (
    <div className="grid3">
      <Card title="Page not found">
        <Link to="/">← Back to the live board</Link>
      </Card>
    </div>
  );
}
