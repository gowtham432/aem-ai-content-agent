# AEM Setup Guide

## Step 1 — Download AEM SDK

Download the AEM as a Cloud Service SDK JAR from the following Google Drive link and request access if needed:

https://drive.google.com/file/d/1eE8e2TI111jxvnB_uU0x1yqj-ZOoOvOX/view?usp=drive_link

## Step 2 — Start AEM

Start AEM by double-clicking the downloaded AEM SDK JAR file.

Wait 3-5 minutes for first startup. AEM will be available at:

```
http://localhost:4502
```

Default credentials: `admin / admin`

## Step 3 — Deploy the demo project

Clone the demo AEM project:

```bash
git clone https://github.com/gowtham432/aem-component-library.git
cd aem-component-library
```

Deploy to your local AEM instance:

```bash
mvn clean install -PautoInstallSinglePackage
```

This installs:

- Page templates
- Core components
- Project structure under `/content/myaemproject`

## Step 4 — Create demo pages

Once deployed, go to AEM Sites:

```
http://localhost:4502/sites.html/content/myaemproject/us/en
```

Create pages with these names and add Text + Accordion components:

- `winter-sale-2022`
- `team-2021`
- `ai-trends-2023`
- `cloud-migration-guide`
- `homepage-banner`

Then set old `cq:lastModified` dates in CRXDE for each page:

```
http://localhost:4502/crx/de/index.jsp
```

| Page | Set `cq:lastModified` to |
| --- | --- |
| `winter-sale-2022` | `2022-12-01T00:00:00.000+00:00` |
| `team-2021` | `2021-06-01T00:00:00.000+00:00` |
| `ai-trends-2023` | `2023-06-01T00:00:00.000+00:00` |
| `cloud-migration-guide` | `2021-03-01T00:00:00.000+00:00` |
| `homepage-banner` | `2022-01-15T00:00:00.000+00:00` |
