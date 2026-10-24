# Third-party notices — NiakPS5

NiakPS5 uses the GPL-3.0-or-later PS5 native UI and GPL-3.0-or-later
`console_curl.c` / `console_curl.h` support written by BlackBearReloaded.
The latter is included under `native/title/vendor/`, sourced from the
GPL-3.0-or-later [Afterglow](https://github.com/DevvNirvana/afterglow)
repository. It provides console DNS, fcntl compatibility and the PS5
certificate-store path for public-media HTTPS. The PS5 app verifies TLS
certificates and names and does not bypass SSL checks.

The PacBrew static dependency chain includes these components. The exact
versions are resolved from the pinned native-toolchain's PacBrew packages
during each build; see the build logs for the resolved package versions.

| Component | Licence | Licence text distributed in `tools/licenses/` |
| --- | --- | --- |
| libcurl | curl licence (MIT/X) | `curl-COPYING.txt` |
| OpenSSL | Apache License 2.0 | `openssl-LICENSE.txt` |
| zlib | zlib licence | `zlib-LICENSE.txt` |
| zstd | BSD-3-Clause | `zstd-LICENSE.txt` |
| libpsl | MIT | `libpsl-COPYING.txt` |
| Public Suffix List data | MPL-2.0 | `publicsuffix-LICENSE.txt` |

The licence texts remain in the source tree under
`native/title/vendor/licenses/` and are copied into the distributed
single-folder PS5 installation. This notice does not replace the
individual components' terms or the project's GPL-3.0 licence.
