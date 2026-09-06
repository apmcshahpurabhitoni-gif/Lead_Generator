# LeadHunter

> Local Business Discovery & Intelligence Platform

**Dashboard Version:** 4.0.0  
**Project Status:** Active Development

LeadHunter helps discover local businesses, organize them into reusable business datasets, research individual leads, identify opportunities, and prepare leads for outreach.

## ✨ Dashboard 4.0

The dashboard has been rebuilt around the current LeadHunter workflow:

- 🏠 **Overview** — system metrics and recent activity
- 🔍 **Find Leads** — discover businesses by category and city
- ◈ **Explore** — browse reusable business datasets and leads
- 📊 **Analytics** — lead, research and opportunity coverage
- 📤 **Outreach** — manage leads through outreach stages
- 🎨 **4 Themes** — Modern Light, Modern Dark, Neo Light and Neo Dark
- ⚙️ **Settings** — accessible from the top-right
- 📱 **Mobile Navigation** — optimized bottom navigation

## 🏢 Lead Datasets

LeadHunter treats local searches as reusable business datasets.

For example:

```text
🦷 Dentist · Jabalpur
92 businesses
```

Refreshing the same category and location should update the dataset rather than create unnecessary duplicate search history.

## 🔎 Lead Intelligence

Lead cards are compact by default and expandable when more detail is needed.

Available intelligence can include:

### Contact
- 📞 Phone
- ✉️ Email
- 🌐 Website
- 📍 Address

### Google Intelligence
- ⭐ Rating
- 💬 Review count
- 🗺️ Maps/profile information
- 🔍 Visibility information

### Review Intelligence
- 😊 Sentiment
- 💬 Owner response rate
- ⚠️ Main complaints
- 👍 Positive topics

### Website Intelligence
- Website availability
- SEO signals
- Conversion signals
- Contact and booking signals

### Opportunities
- SEO
- Google Business Profile
- Website
- Automation
- Reputation
- Visibility

## 🔌 Architecture

```text
LeadHunter Main App / Bot / Dashboard
                │
                ▼
          Research Client
                │
                ▼
          Research Worker
        ┌───────┴────────┐
        ▼                ▼
     SearXNG       Intelligence Modules
                     ├── Website Analysis
                     ├── Maps Adapter
                     └── Review Analysis
```

The dashboard consumes normalized LeadHunter data and does not directly depend on third-party provider schemas.

## 🛡️ Data Rules

LeadHunter must not fabricate:

- Google rankings
- Maps rankings
- Review history
- Owner response rates
- Competitor information
- Website findings

When intelligence is unavailable, the UI should clearly display it as unavailable.

## 📁 Dashboard Files

```text
dashboard.py
dashboard_ui/
├── __init__.py
├── api.py
└── templates.py
```

## 🚀 Local Testing

Install project dependencies, then:

```bash
uvicorn dashboard:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Check dashboard health:

```text
/api/health
```

## ⚠️ Backend Wiring

Dashboard 4.0 is designed to connect to the existing LeadHunter backend modules:

- `database.py`
- `lead_workflow.py`
- `discovery.py`
- `research_client.py`

The dashboard API adapter must use the actual function names and return schemas from the repository.

## 🧪 Before Deployment

Verify:

1. Dashboard loads.
2. `/api/health` returns successfully.
3. Find Leads reaches the discovery workflow.
4. Explore loads real saved leads.
5. Research reaches the Research Worker.
6. Missing intelligence is not shown as fake data.
7. Theme switching works.
8. Mobile navigation works.
9. Environment variables are configured.
10. Version references are synchronized.

## 📚 Documentation

The Local Intelligence architecture is documented separately in:

**LeadHunter Local Intelligence Documentation Pack v1.0.0**

It covers:

- Integration architecture
- Unified Research API
- Maps provider adapter
- Review intelligence
- Website intelligence
- Opportunity engine
- Security and deployment
- Testing
- Dashboard wiring

## 🔐 Security

Never commit API keys, passwords, tokens or other secrets to GitHub.

Use environment variables for service configuration and credentials.

---

**LeadHunter 4.0.0 — Local Business Discovery & Intelligence**
