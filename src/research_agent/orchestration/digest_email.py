from __future__ import annotations

import time

from research_agent.app.watchdog_storage import WatchdogDigest


def build_html_digest_email(digest: WatchdogDigest) -> str:
    """Build a rich HTML email from a watchdog digest.

    Args:
        digest: The watchdog digest to format.

    Returns:
        HTML string suitable for email.
    """
    papers_html = ""
    if digest.new_papers:
        for paper in digest.new_papers[:20]:
            title = paper.get("title", "Untitled")
            authors = paper.get("authors", [])
            if isinstance(authors, list):
                authors_str = ", ".join(authors[:4])
                if len(authors) > 4:
                    authors_str += " et al."
            else:
                authors_str = str(authors)
            year = paper.get("year", "n.d.")
            url = paper.get("url", "")
            snippet = paper.get("snippet", "")
            provider = paper.get("watchdog_provider", paper.get("provider", "unknown"))
            score = paper.get("relevance_score", None)

            score_badge = ""
            if score is not None:
                pct = round(score * 100)
                color = "#34d399" if score >= 0.7 else "#f59e0b" if score >= 0.4 else "#a1a1aa"
                score_badge = f'<span style="display: inline-block; background: {color}22; color: {color}; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; margin-left: 8px;">{pct}% match</span>'

            snippet_html = ""
            if snippet:
                snippet_clean = snippet[:200]
                if len(snippet) > 200:
                    snippet_clean += "..."
                snippet_html = f'<p style="margin: 4px 0 0 0; font-size: 13px; color: #71717a; line-height: 1.4;">{snippet_clean}</p>'

            provider_badge = provider.replace("_", " ").title()

            papers_html += f"""
        <tr>
          <td style="padding: 16px 20px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; margin-bottom: 12px; display: block;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td>
                  <a href="{url}" style="color: #818cf8; text-decoration: none; font-size: 15px; font-weight: 600; line-height: 1.3;">{title}</a>{score_badge}
                </td>
              </tr>
              <tr>
                <td style="padding-top: 6px;">
                  <span style="font-size: 12px; color: #a1a1aa;">{authors_str}</span>
                  <span style="font-size: 12px; color: #52525b; margin: 0 6px;">&middot;</span>
                  <span style="font-size: 12px; color: #a1a1aa;">{year}</span>
                  <span style="font-size: 12px; color: #52525b; margin: 0 6px;">&middot;</span>
                  <span style="font-size: 12px; color: #71717a; background: rgba(255,255,255,0.04); padding: 1px 6px; border-radius: 4px;">{provider_badge}</span>
                </td>
              </tr>
              {f'<tr><td>{snippet_html}</td></tr>' if snippet_html else ''}
            </table>
          </td>
        </tr>"""

    generated_date = time.strftime("%B %d, %Y at %H:%M UTC", time.gmtime(digest.generated_at))

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #050505; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #050505;">
    <tr>
      <td align="center" style="padding: 40px 24px;">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">
          <!-- Header -->
          <tr>
            <td style="text-align: center; padding-bottom: 32px;">
              <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #f4f4f5; letter-spacing: -0.03em;">Research Watchdog</h1>
              <p style="margin: 8px 0 0 0; font-size: 14px; color: #a1a1aa;">Automated literature monitoring digest</p>
            </td>
          </tr>

          <!-- Digest Summary Card -->
          <tr>
            <td style="background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(59,130,246,0.08)); border: 1px solid rgba(139,92,246,0.2); border-radius: 12px; padding: 24px; margin-bottom: 24px; display: block;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #e4e4e7;">{digest.topic}</h2>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #a1a1aa;">Generated {generated_date}</p>
                  </td>
                  <td align="right" style="width: 80px;">
                    <div style="background: rgba(139,92,246,0.2); border-radius: 50%; width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; text-align: center;">
                      <span style="font-size: 24px; font-weight: 800; color: #c4b5fd;">{digest.paper_count}</span>
                    </div>
                  </td>
                </tr>
              </table>
              <p style="margin: 16px 0 0 0; font-size: 14px; color: #d4d4d8; line-height: 1.5;">{digest.summary}</p>
            </td>
          </tr>

          <!-- Papers List -->
          {'<tr><td><h3 style="margin: 24px 0 16px 0; font-size: 16px; font-weight: 700; color: #f4f4f5;">New Papers</h3></td></tr>' if papers_html else ''}
          {papers_html}

          <!-- Footer -->
          <tr>
            <td style="padding-top: 32px; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #52525b;">
                This is an automated digest from Research Agent. You received this because you subscribed to monitoring for "{digest.topic}".
              </p>
              <p style="margin: 8px 0 0 0; font-size: 12px; color: #52525b;">
                To unsubscribe, visit your Research Agent Watchdog dashboard and disable notifications for this topic.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
