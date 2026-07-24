# InkPi Code Of Conduct

## Our Standard

Contributors and automation agents must keep collaboration respectful,
technical, and focused on improving InkPi. Communicate assumptions clearly,
welcome correction, and criticize designs or code rather than people.

Expected behavior includes:

- preserving user work and repository history;
- explaining risky or operationally disruptive changes before applying them;
- reporting failures, uncertainty, and incomplete verification honestly;
- keeping reviews actionable and grounded in evidence;
- respecting privacy, credentials, and deployment access;
- favoring maintainable solutions over personal preference.

Unacceptable behavior includes harassment, discrimination, personal attacks,
deliberate disruption, exposing secrets, or knowingly misrepresenting system
state or test results.

## Operational Responsibility

InkPi controls physical hardware and system services. Contributors must:

- avoid concurrent processes that can contend for SPI/GPIO ownership;
- preserve a rollback path for deployment changes;
- avoid destructive commands unless explicitly authorized;
- treat network configuration, credentials, and privileged helpers as
  security-sensitive;
- distinguish simulation results from physical-hardware verification.

## Enforcement

Project maintainers may reject, revert, or restrict contributions that violate
this code of conduct or create unacceptable operational risk. Concerns should
be raised privately with the project owner when public discussion would expose
personal, credential, or security-sensitive information.
