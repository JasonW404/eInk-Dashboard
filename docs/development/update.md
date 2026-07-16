# InkPi v1.0 Architecture & Implementation Handoff

## 1. Project Overview

InkPi is a personal ambient productivity terminal based on Raspberry Pi + eInk display.

The system consists of:

* Raspberry Pi with Waveshare 4.26" ePaper HAT (800×480)
* Ubuntu workstation as optional compute node
* Web management interface
* eInk display runtime

The design goal:

> Build a local-first, low-power, AI productivity dashboard that continuously displays important personal information without requiring active interaction.

InkPi is **not** designed as:

* a server monitoring dashboard
* a NAS management panel
* a generic IoT platform

The primary usage scenarios:

* Codex usage tracking
* GitHub contribution/activity
* TODO management
* Agent workflow status (future)
* Personal productivity information display

---

# 2. Core Architecture Principles

## 2.1 Raspberry Pi is the Core Device

Raspberry Pi owns:

* application state
* user interaction
* configuration
* display lifecycle
* eInk hardware

Ubuntu is only an external compute/data provider.

---

## 2.2 Single Source of Data

All application state is stored on Raspberry Pi.

Example:

```
SQLite Database
        |
        |
        +---- Web UI
        |
        +---- eInk Renderer
        |
        +---- Display Service
```

No component should maintain independent state.

---

## 2.3 Web UI and eInk UI Are Different Views

Important:

Do NOT reuse the same React component for Web Dashboard and eInk Display.

They share:

* domain models
* API data

But have different UI components.

Reason:

Web UI:

* optimized for human interaction
* responsive
* interactive

eInk UI:

* fixed 800×480
* hardware constrained
* optimized for readability

Architecture:

```
                Domain Data
                     |
          +----------+----------+
          |                     |
          v                     v

 Web Components          eInk Components

 Human Dashboard        Device Layout

```

---

# 3. High-Level Architecture

```
                         Browser

                            |
                            |
                    React Web Application

                            |
                            |
                    Raspberry Pi API

                            |
             +--------------+--------------+

             |                             |

        SQLite Database              eInk Runtime


                                             |
                                             |
                                  GET PNG Endpoint

                                             |
                                             |

                                  Waveshare Driver


Ubuntu Host

      |
      |
Host Agent

      |
      |
Collectors

- Codex Collector
- GitHub Collector
- Future Agent Collectors

```

---

# 4. Raspberry Pi Components

## 4.1 InkPi API Server

Technology:

Recommended:

* FastAPI
* SQLite
* SQLAlchemy / SQLModel

Responsibilities:

* REST API
* Web backend
* Data persistence
* Host Agent communication
* eInk image endpoint

Does NOT:

* control eInk directly
* execute refresh logic
* manage GPIO

---

## 4.1.1 API Responsibilities

### TODO API

Example:

```
GET    /api/todos

POST   /api/todos

PATCH  /api/todos/{id}

DELETE /api/todos/{id}
```

---

### Host Agent API

Agent registration:

```
POST /api/agents/register
```

Heartbeat:

```
POST /api/agents/{id}/heartbeat
```

Data upload:

```
POST /api/agents/{id}/reports
```

---

### Display API

Display revision:

```
GET /api/display/revision
```

Response:

```json
{
  "revision": 102,
  "updated_at": "2026-07-15T10:00:00"
}
```

Display image:

```
GET /api/display/image
```

Response:

```
image/png

800x480
```

Important:

Display Service pulls this endpoint.

API never pushes images.

---

# 5. Web Application

Technology:

Recommended:

* React
* TypeScript
* Vite
* Tailwind or CSS Modules

Font:

Global:

```
JetBrains Mono
```

No other font.

---

# 5.1 Web Pages

Only three pages:

```
/
 |
 +-- Overview

/todo

/settings
```

Do not create additional tabs.

---

# 5.2 Overview Page

Purpose:

Quick status overview.

Structure:

```
Overview

|
+-- InkPi Status
|
+-- Codex Usage
|
+-- GitHub Activity
|
+-- TODO Summary
|
+-- eInk Preview
|
+-- Last Sync Information

```

Important:

The eInk Preview is placed at the bottom.

It is NOT the primary dashboard.

---

## Overview Components

Example:

```
components/

overview/

    InkPiStatusCard.tsx

    CodexCard.tsx

    GithubCard.tsx

    TodoSummary.tsx

    EinkPreview.tsx

```

---

# 5.3 TODO Page

Purpose:

Manage TODO items.

Features:

* create
* edit
* delete
* complete
* reorder

Each TODO contains:

```json
{
"id":1,
"title":"Refactor SDK",
"completed":false,
"display_on_eink":true
}
```

`display_on_eink`

Controls whether the item appears on the eInk screen.

---

# 5.4 Settings Page

Only:

## Device

```
Device Name

Timezone

Firmware Version
```

## Network

WiFi hotspot:

```
Enable / Disable

SSID

Password

Connected Clients

QR Code
```

## System Info

Display:

```
Last refresh

Current revision

Device uptime
```

Do NOT expose:

* refresh interval
* partial refresh count
* full refresh policy

These belong to Display Service.

---

# 6. eInk Rendering System

## 6.1 eInk Components

Location:

```
components/eink/
```

Example:

```
EinkDisplay.tsx

GithubBlock.tsx

CodexBlock.tsx

TodoBlock.tsx

SystemBlock.tsx
```

Requirements:

Fixed size:

```
800 x 480
```

No responsive layout.

---

# 6.2 eInk Design Rules

Font:

```
JetBrains Mono
```

Color:

Only:

```
Black
White
Gray
```

Avoid:

* animations
* gradients
* shadows
* rounded cards

---

# 6.3 PNG Generation

Do NOT use:

* PIL
* Python image drawing

Use:

React rendering.

Recommended implementation:

```
Chromium Headless
+
Playwright
```

Flow:

```
Display Service

        |
        |
GET /api/display/image


        |

Open eInk Render Page


        |

Screenshot


        |

PNG


        |

eInk Driver

```

---

# 7. Display Service

Independent process.

Example:

```
inkpi-display.service
```

Responsibilities:

## Refresh Scheduling

Controls:

* debounce
* refresh interval
* dirty checking

Example:

```
TODO changed

      |

dirty=true


      |

wait debounce


      |

refresh once

```

---

## Refresh Strategy

Must preserve existing project logic.

Separate module:

```
display/

    strategy/

        scheduler.py

        partial_refresh.py

        full_refresh.py

```

Responsibilities:

* partial refresh
* full refresh
* ghosting control
* refresh history

Do not move this logic into API.

---

## Display Loop

Pseudo:

```python

while True:

    if refresh_strategy.should_refresh():

        revision = get_revision()


        if revision_changed:

            image = GET("/api/display/image")


            eink.display(image)


    sleep()

```

---

# 8. Ubuntu Host Agent

Purpose:

Provide external data.

Runs:

```
inkpi-host-agent.service
```

Does NOT:

* host Web service
* control display
* store application state

---

# 8.1 Collector Architecture

```
host-agent

    |
    |
    +-- CodexCollector

    +-- GithubCollector

    +-- FutureCollector

```

Interface:

```python
class Collector:

    name:str

    interval:int


    async def collect():
        pass

```

---

# 8.2 Current Collectors

## Codex Collector

Collect:

* weekly usage
* reset time
* plan

---

## GitHub Collector

Collect:

* contribution calendar
* PR count
* changed lines
* repository activity

---

# 9. Network Architecture

Current:

```
Ubuntu
 |
 | Ethernet
 |
Raspberry Pi

 |
 |
WiFi Hotspot

 |
 |
Mobile Device

```

---

# 9.1 Hotspot Management

Web UI controls:

* enable
* disable
* SSID
* password

Implementation:

Do not run API as root.

Use:

```
InkPi API

    |

Network Helper

    |

NetworkManager

```

---

# 10. Database Design

SQLite.

Main tables:

## todos

```
id

title

completed

display_on_eink

created_at

updated_at

```

## agents

```
id

name

token

last_seen

```

## reports

```
id

agent_id

type

payload

created_at

expires_at

```

## display_state

```
revision

last_refresh

last_full_refresh

refresh_count

```

---

# 11. Suggested Repository Structure

```
inkpi/

├── apps/

│   ├── api/

│   ├── web/

│   ├── display/

│   └── host-agent/


├── packages/

│   ├── domain/

│   └── api-client/


├── deploy/

│   ├── raspberry-pi/

│   └── ubuntu/

└── docs/

```

---

# 12. Development Priority

## Phase 1

Foundation:

* API Server
* SQLite
* React Web
* TODO CRUD

---

## Phase 2

Display:

* eInk Components
* Playwright PNG export
* Display Service migration

---

## Phase 3

Host Agent:

* Codex Collector
* GitHub Collector

---

## Phase 4

Network:

* WiFi hotspot management

---

# Final Definition

InkPi v1.0 is:

> A Raspberry Pi centered ambient AI productivity terminal. The Raspberry Pi owns state and hardware lifecycle. Ubuntu provides optional computational capabilities. React provides both human-facing dashboard views and fixed eInk rendering views. Display Service independently controls refresh timing and hardware behavior.

The implementation should prioritize:

1. Stability
2. Long-running reliability
3. Single source of truth
4. UI consistency
5. Hardware-aware refresh management

Do not optimize prematurely for distributed architecture. This is a personal device, not a cloud platform.
