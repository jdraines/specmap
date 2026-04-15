import { useLocation } from 'react-router';
import { RepoPage } from './RepoPage';
import { PRReviewPage } from './PRReviewPage';

/**
 * Parses the splat path under /r/* to route to RepoPage or PRReviewPage.
 * Supports nested namespaces like: group/subgroup/project or group/subgroup/project/pull/42
 */
export function RepoSplatRouter() {
  const location = useLocation();
  // Strip the /r/ prefix to get the splat
  const splat = location.pathname.replace(/^\/r\//, '');

  // Check for /pull/{number} suffix
  const pullMatch = splat.match(/^(.+)\/pull\/(\d+)$/);
  if (pullMatch) {
    const fullName = pullMatch[1];
    const number = parseInt(pullMatch[2], 10);
    return <PRReviewPage fullName={fullName} prNumber={number} />;
  }

  // Otherwise it's a repo page
  return <RepoPage fullName={splat} />;
}
