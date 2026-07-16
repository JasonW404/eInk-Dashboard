# InkPi Web UI/UX Design Specification

## 1. Overall Design Philosophy

InkPi Web is not a traditional admin dashboard.

Design goal:

> Provide a calm, information-dense, personal productivity control interface that matches the eInk device experience.

The design should feel like:

* a personal workstation dashboard
* a developer tool
* an ambient computing companion

Avoid:

* SaaS dashboard style
* colorful analytics panels
* excessive cards
* dense tables
* complex navigation

---

# 2. Global Design System

## 2.1 Typography

The entire application uses:

```
JetBrains Mono
```

No other fonts.

Reason:

* maintain consistency with eInk display
* developer-oriented visual identity
* predictable character width

Font weights:

| Usage         | Weight   |
| ------------- | -------- |
| Page title    | Bold     |
| Section title | SemiBold |
| Data value    | Bold     |
| Description   | Regular  |
| Metadata      | Regular  |

---

## 2.2 Color System

InkPi uses monochrome-first design.

Primary:

```
Background:
#FFFFFF

Foreground:
#000000

Secondary text:
#666666

Border:
#D9D9D9

Disabled:
#AAAAAA
```

Status colors are allowed only for system states:

```
Online:
dark green

Warning:
dark yellow

Error:
dark red
```

Do not use gradients.

Do not use shadows.

Do not use glassmorphism.

---

## 2.3 Layout Style

General characteristics:

* large whitespace
* clear separators
* thin borders
* monospaced alignment
* rectangular structure

Avoid:

* rounded modern SaaS cards
* floating panels
* excessive icons

Recommended border:

```
1px solid #D9D9D9
```

Border radius:

```
0-4px
```

---

# 3. Navigation Structure

Only three pages exist.

No additional tabs.

Navigation:

```
InkPi

[Overview]

[Todo List]

[Settings]
```

Desktop:

Left sidebar.

Mobile:

Top navigation or bottom navigation.

---

# 4. Overview Page

## Purpose

The Overview page is the primary entry point.

When user opens InkPi, they should immediately understand:

* device status
* productivity status
* important information
* current eInk output

---

# Desktop Layout

Recommended viewport:

```
1440 × 960
```

Structure:

```
+------------------------------------------------+
| InkPi                                          |
| Ambient Productivity Terminal                 |
+------------------------------------------------+

+------------------------------------------------+
| Device Status                                  |
|                                                |
| ONLINE                                         |
| Last sync: 10 seconds ago                      |
|                                                |
+------------------------------------------------+

+------------------------------------------------+
| Codex Usage                                    |
|                                                |
| Weekly Usage                                   |
| ████████████░░░░                              |
|                                                |
| Reset: 2d 13h                                  |
+------------------------------------------------+

+------------------------------------------------+
| GitHub Activity                                |
|                                                |
| Contributions                                  |
| PRs                                            |
| Commits                                        |
+------------------------------------------------+

+------------------------------------------------+
| TODO Summary                                   |
|                                                |
| Today                                          |
|                                                |
| □ Finish architecture document                 |
| □ Review PR                                    |
| ☑ Update README                                |
+------------------------------------------------+

+------------------------------------------------+
| eInk Preview                                   |
|                                                |
| +--------------------------------------------+ |
| |                                            | |
| |        800 × 480 preview                   | |
| |                                            | |
| +--------------------------------------------+ |
|                                                |
| Revision: #102                                |
| Generated: 10:32:12                           |
+------------------------------------------------+

```

---

# Important:

The eInk Preview section MUST be placed at the bottom.

Reason:

It is a debugging/verification tool.

It is not the main dashboard.

---

# 5. Overview Components

## 5.1 Device Status Component

Purpose:

Show InkPi health.

Content:

```
InkPi

ONLINE

IP:
10.42.0.246

Last heartbeat:
10s ago

Version:
v1.0
```

---

## 5.2 Codex Usage Component

Purpose:

Show AI coding usage.

Example:

```
CODEX

Weekly Usage

████████░░░░░░

72%

Reset:
Tomorrow 08:00
```

Do not show:

* raw logs
* token history table

---

## 5.3 GitHub Activity Component

Example:

```
GITHUB

This Week

Commits:
23

PR:
5

Contribution:
███████░░
```

---

## 5.4 TODO Summary Component

Only show:

* today's TODO
* important unfinished items

Example:

```
TODO

Today

□ Refactor Agent Context

□ Finish Design

☑ Review PR
```

---

# 6. Todo List Page

Purpose:

Full TODO management.

Layout:

```
+--------------------------------------------+
| Todo List                                  |
+--------------------------------------------+

[ + New Todo ]


TODAY

--------------------------------------------

□ Refactor Agent Runtime

  Created:
  2026-07-15

  Display:
  ON EINK


--------------------------------------------

□ Update Documentation

  Display:
  OFF

```

---

# TODO Item Interaction

Each item supports:

* edit
* delete
* complete
* reorder

Additional property:

```
Display on eInk
```

UI:

```
Display on eInk

[ON]
```

or:

```
☑ Show on InkPi
```

---

# 7. Settings Page

Purpose:

Device configuration.

Only three sections.

---

# 7.1 Device Settings

```
DEVICE


Name

InkPi


Timezone

Asia/Shanghai


Firmware

v1.0
```

---

# 7.2 Network Settings

Purpose:

Manage Raspberry Pi WiFi hotspot.

Layout:

```
NETWORK


WiFi Hotspot


Status:

ON


SSID:

InkPi-AP


Password:

********


Connected Devices:

2


[Generate QR Code]

```

Controls:

Allowed:

* enable hotspot
* disable hotspot
* change SSID
* change password

Not included:

* routing table
* firewall rules
* advanced network config

---

# 7.3 Display Information

Read-only.

Example:

```
DISPLAY


Resolution:

800 × 480


Last Refresh:

10:32:10


Current Revision:

#102


Refresh Mode:

Partial


```

Important:

The user cannot modify:

* refresh interval
* debounce time
* partial refresh count
* full refresh policy

These belong to Display Service.

---

# 8. Mobile Layout

Target:

```
390 × 844
```

Principles:

* single column
* no horizontal scrolling
* same information hierarchy

---

## Mobile Overview

Order:

```
Device Status

Codex Usage

GitHub Activity

TODO Summary

eInk Preview

```

---

## Mobile Navigation

Bottom navigation:

```
-----------------

Overview

Todo

Settings

-----------------
```

---

# 9. eInk Preview Component Specification

This is NOT a responsive component.

Fixed:

```
width: 800px

height: 480px
```

Purpose:

Preview exactly what the physical display receives.

Rendering:

```
Same data source
        |
        |
eInk Component
        |
        |
PNG Export
```

---

# 10. Relationship Between Web UI and eInk UI

Important implementation rule:

Do NOT:

```
Web Screenshot
       |
       |
       v
eInk
```

Do:

```
              Domain Data

                  |

       +----------+----------+

       |                     |

       v                     v


 Web Components       eInk Components


       |                     |

 Browser UI          PNG Export


```

---

# 11. Expected Visual Result

The final product should feel like:

* a developer's personal command center
* a physical eInk terminal companion
* a calm productivity tool

It should NOT feel like:

* Grafana
* Home Assistant dashboard
* Enterprise admin panel
* SaaS analytics product
