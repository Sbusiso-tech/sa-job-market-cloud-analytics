import { Link } from 'react-router-dom';
import { EmptyState } from '../components/StatusViews';

export default function NotFound() {
  return (
    <EmptyState title="Page not found">
      <p>The page you are looking for does not exist or has moved.</p>
      <p>
        <Link to="/" className="btn btn--primary">
          Go to the dashboard
        </Link>
      </p>
    </EmptyState>
  );
}
