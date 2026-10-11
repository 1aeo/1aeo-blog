"""Builds site/blog/securing-fresh-ubuntu-vm-tor-relay-checklist.html. Run: python3 build.py (PART2_LIVE=1 links Part 2)."""
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root
SLUG = "securing-fresh-ubuntu-vm-tor-relay-checklist.html"
OUT = ROOT / "site" / "blog" / SLUG
ADV = "advanced-hardening-tor-relay-operators.html"
import os
PART2_LIVE = os.environ.get("PART2_LIVE", "0") == "1"   # unlink Part 2 until it is published
TITLE = "Securing a Fresh Ubuntu VM for a Tor Relay: A Beginner's Checklist"
DESC = "Harden a new Ubuntu 24.04/26.04 VM for a Tor relay: unique passwords, key-only SSH, two open ports, Tor from deb.torproject.org, and the checks that prove it."
CHART = "images/tor-relay-intrusions-oct-2026-chart-exit-policies.png"
ALT = ("Hourly chart, September 30 to October 10 2026 (UTC), of how many relays in each Tor consensus advertised either of two "
       "exit policies written by the intruders, both open to SSH so the relays could intercept SSH logins made through Tor and steal the credentials. None before October 1; the count jumps on October 2, peaks at "
       "353 relays on October 4, then drops away as the directory authorities act. None are left from 17:00 UTC on October 5, "
       "shortly before the Tor Project's warning at 17:50, and the count stays at zero through October 10.")

def pre(code):
    return "<pre><code>" + html.escape(code.strip("\n"), quote=False) + "</code></pre>\n"

def h2(id_, text):
    return f'<h2 id="{id_}">{text} <a class="anchor" href="#{id_}" aria-label="Link to this section">#</a></h2>\n'

L = []
a = L.append

a(h2("why-now", "Why Now"))
a(f"""<p>Between October 1 and 4, 2026, <strong class="highlight">377 relays run by 59 operators</strong> switched to one of two exit policies that open SSH (<a href="https://lists.torproject.org/mailman3/hyperkitty/list/tor-relays@lists.torproject.org/message/Z2B6XYKJZBBQADU77MSNL6FJP7MHZHIV/">our analysis</a>). On October 5 the Tor Project <a href="https://forum.torproject.org/t/tor-relays-security-incident-affecting-some-relay-operators/22231">warned</a> that attackers were breaking into Linux relay hosts and editing <code>torrc</code> so the relays would intercept SSH logins made through Tor, and <a href="https://forum.torproject.org/t/tor-relays-re-ebury-1-8-3-on-two-quetzalcoatl-relay-servers-timeline-lessons-open-questions/22243">one victim's</a> captured credentials were then used to log in to his server. The directory authorities removed the relays.</p>
<img width="2080" height="1120" src="{CHART}" alt="{html.escape(ALT)}">
<p>The one break-in documented in detail (<a href="https://forum.torproject.org/t/tor-relays-ebury-1-8-3-on-two-quetzalcoatl-relay-servers-timeline-lessons-open-questions/22238">post-mortem</a>) began with <strong class="highlight">one password reused</strong> for SSH, sudo and backups, with SSH password logins on. The attacker then installed <strong>Ebury 1.8.3</strong>, an OpenSSH backdoor that records every password typed into <code>sshd</code> and hides from the host. 81 of the other operators' 100 affected relays were at <a href="https://metrics.1aeo.com/as/AS53667/">FranTech Solutions (BuyVM), AS53667</a>; whether the provider itself was breached is unconfirmed.</p>
""")

a(h2("prepare", "1. Prepare"))
a("""<ul>
  <li><strong>Unique passwords, kept in a password manager.</strong> Never reuse one, and never put one in a script or file on a server. Turn on two-factor login for your hosting account and the email that can reset it: the provider's console is root on your VM.</li>
  <li><strong>Make an SSH key on your own computer</strong> (set a passphrase when asked) and paste the <code>.pub</code> file's contents into the provider's SSH-key field when you create the VM:</li>
</ul>
""")
a(pre('ssh-keygen -t ed25519 -C "relay01"'))
a("""<ul>
  <li><strong>Pick Ubuntu's official 24.04 or 26.04 image</strong> on a full VM, and run nothing else on it.</li>
</ul>
""")

a(h2("ssh", "2. Lock SSH to Keys"))
a("""<p>Log in with the account your provider gave you, usually <code>root</code> or <code>ubuntu</code>. On the first connection, check that the fingerprint <code>ssh</code> shows matches the one in the provider's console or boot log. Then update, add an admin user with your key, and lock SSH to keys:</p>
""")
a(pre("""
sudo apt update && sudo apt full-upgrade -y && sudo apt install -y ufw gnupg && sudo reboot    # then log back in
"""))
a(pre("""
sudo adduser relayadmin          # give it a unique password: sudo will ask for it
sudo usermod -aG sudo relayadmin
sudo cp -r ~/.ssh /home/relayadmin/ && sudo chown -R relayadmin:relayadmin /home/relayadmin/.ssh
sudo passwd -l root
"""))
a(pre("""
sudo tee /etc/ssh/sshd_config.d/00-hardening.conf >/dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers relayadmin
DisableForwarding yes
LogLevel VERBOSE
EOF
sudo sshd -t && sudo systemctl reload ssh
"""))
a("""<p>Keep this session open, and check that <code>ssh relayadmin@192.0.2.10</code> (your server's IP) works from a second terminal. From now on, use only <code>relayadmin</code>. Two rules come straight from the break-in above:</p>
<ul>
  <li><strong>If SSH ever asks this server for a password, stop.</strong> Your server never will, so something else is answering.</li>
  <li><strong>The relay is a destination, never a starting point.</strong> Never <code>ssh</code> or <code>scp</code> <em>from</em> it, and never use <code>ssh -A</code>.</li>
</ul>
""")

a(h2("firewall", "3. Open Two Ports"))
a(pre("""
sudo ufw default deny incoming
sudo ufw allow 443/tcp       # Tor
sudo ufw limit 22/tcp        # SSH, with brute-force limiting
sudo ufw --force enable
"""))
a("<p>If you always connect from the same address, allow SSH only from there (your address in place of 203.0.113.25): <code>sudo ufw allow from 203.0.113.25 to any port 22 proto tcp</code>, then <code>sudo ufw delete limit 22/tcp</code>. If that address ever changes, log in through your provider's web console as <code>relayadmin</code> to update the rule.</p>\n")

a(h2("tor", "4. Install Tor From the Tor Project"))
a("<p>Ubuntu's own <code>tor</code> lags behind the Tor Project's security fixes, and the Tor Project <a href=\"https://support.torproject.org/little-t-tor/getting-started/installing/\">says to install from its own repository instead</a>. Add it, and check its key before you install anything:</p>\n")
a(pre("""
. /etc/os-release
sudo tee /etc/apt/sources.list.d/tor.sources >/dev/null <<EOF
Types: deb
URIs: https://deb.torproject.org/torproject.org/
Suites: ${VERSION_CODENAME}
Components: main
Signed-By: /usr/share/keyrings/deb.torproject.org-keyring.gpg
EOF
curl -fsSL https://deb.torproject.org/torproject.org/A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89.asc \\
  | gpg --dearmor | sudo tee /usr/share/keyrings/deb.torproject.org-keyring.gpg >/dev/null
gpg --show-keys /usr/share/keyrings/deb.torproject.org-keyring.gpg
# stop unless the line under "pub" reads A3C4F0F979CAA22CDBA8F512EE8CBC9E886DDD89
"""))
a("<p>Install Tor, let Ubuntu's automatic updates include it, and give it a minimal config:</p>\n")
a(pre("""
sudo apt update && sudo apt install -y tor deb.torproject.org-keyring
echo 'Unattended-Upgrade::Allowed-Origins { "TorProject:${distro_codename}"; };' \\
  | sudo tee /etc/apt/apt.conf.d/52unattended-upgrades-tor >/dev/null
sudo tee /etc/tor/torrc >/dev/null <<'EOF'
Nickname      myRelay01
ContactInfo   email:tor[]example.com ciissversion:3
ORPort        443
ExitRelay     0
SocksPort     0
EOF
sudo systemctl restart tor@default
sudo journalctl -u tor@default -f      # wait for "...reachable from the outside. Excellent.", then Ctrl+C
"""))

a(h2("check", "5. Prove It, Then Check Monthly"))
a("<p>Reboot, then confirm each row. The last one works once the relay is published, about three hours after Tor first starts. <code>sudo cat /var/lib/tor/fingerprint</code> shows its FINGERPRINT.</p>\n")
a("""<div class="table-wrap">
<table>
  <thead><tr><th>Check</th><th>Expect</th></tr></thead>
  <tbody>
    <tr><td><code>sudo ss -tlnpH | grep -vE '127\\.0\\.0\\.|\\[::1\\]'</code></td><td>only SSH (<code>sshd</code>, <code>systemd</code>) and <code>tor</code></td></tr>
    <tr><td><code>ssh -o BatchMode=yes -o PubkeyAuthentication=no relayadmin@192.0.2.10</code> (from your computer)</td><td><code>Permission denied (publickey).</code></td></tr>
    <tr><td><code>apt-cache policy tor</code></td><td>installed from <code>deb.torproject.org</code></td></tr>
    <tr><td><code>curl -s "https://onionoo.torproject.org/details?lookup=FINGERPRINT&amp;fields=flags,exit_policy_summary"</code></td><td>no <code>"Exit"</code> flag; <code>{"reject":["1-65535"]}</code></td></tr>
  </tbody>
</table>
</div>
<p>Every month, and whenever <a href="https://lists.torproject.org/mailman3/postorius/lists/tor-relays.lists.torproject.org/">tor-relays</a> reports an incident:</p>
<ul>
  <li><strong>Rerun the last row.</strong> It's the one check an intruder can't fake, and the way this incident was caught. Sign up for <a href="https://weather.torproject.org/">Tor Weather</a> to be emailed if the relay goes offline.</li>
  <li><strong>Run the quick Ebury check</strong> below. Log in with your key and type no password. It runs the checks in a fresh shell that current Ebury builds don't hide from. A clean result is no guarantee; """ + ('<a href="' + ADV + '#ebury">Part 2</a> goes deeper' if PART2_LIVE else 'Part 2 (coming soon) goes deeper') + """.</li>
</ul>
""")
a(pre("""
H=1 I=1 LD_PRELOAD=":" LD_DEBUG=":" bash -c '
find /usr/lib -name "libkeyutils*" -perm -4000 2>/dev/null   # must print nothing
grep -E "@event-|@/dev/(event|stats)-" /proc/net/unix         # must print nothing
grep -rniE "^\\s*(%include|ExitRelay|ExitPolicy)" /etc/tor/     # only "ExitRelay 0"
'
"""))

a("""<h3 id="if-compromised">If Something Is Off <a class="anchor" href="#if-compromised" aria-label="Link to this section">#</a></h3>
<ol>
  <li>Type no password into that host. Snapshot its disk in the provider panel, then power it off.</li>
  <li>Email <code>bad-relays@lists.torproject.org</code> with the fingerprint, the IP address and what you found.</li>
  <li>Rebuild on a fresh VM with this checklist and a <strong>new</strong> relay identity.</li>
  <li>Change every password you typed there. Once you're clean, ask <code>bad-relays@</code> to lift any block on your IP address.</li>
</ol>
""")
a("""<p class="refs">References: Tor Project <a href="https://forum.torproject.org/t/tor-relays-security-incident-affecting-some-relay-operators/22231">incident notice</a>, <a href="https://community.torproject.org/relay/setup/guard/debian-ubuntu/">Debian/Ubuntu relay guide</a>, <a href="https://support.torproject.org/little-t-tor/getting-started/installing/">package repository</a>, <a href="https://community.torproject.org/relay/setup/guard/debian-ubuntu/updates/">automatic updates</a> and <a href="https://community.torproject.org/relay/community-resources/bad-relays/">bad-relay reporting</a>; the <a href="https://forum.torproject.org/t/tor-relays-ebury-1-8-3-on-two-quetzalcoatl-relay-servers-timeline-lessons-open-questions/22238">Ebury 1.8.3 post-mortem</a>; ESET, <a href="https://www.welivesecurity.com/en/eset-research/ebury-alive-unseen-400k-linux-servers-compromised-cryptotheft-financial-gain/">"Ebury is alive but unseen"</a> (2024); exit-policy counts from Tor's public <a href="https://collector.torproject.org/">CollecTor</a> archives.</p>
""")

body = "".join(L)
out, inpre = [], False
for ln in body.split("\n"):
    starts = "<pre>" in ln
    out.append(("    " + ln) if (not inpre and ln.strip()) else ln)
    if starts: inpre = True
    if "</pre>" in ln: inpre = False
body = "\n".join(out)

PART2_HTML = (f'<a href="{ADV}">Advanced Hardening for Tor Relay Operators</a>' if PART2_LIVE else "<strong>Advanced Hardening for Tor Relay Operators</strong> (coming soon)")
css = (ROOT / "templates" / "house-style.html").read_text()
nav = (ROOT / "templates" / "nav.html").read_text()
page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{TITLE} | 1st Amendment Encrypted Openness</title>
  <meta name="description" content="{html.escape(DESC)}">
  <link rel="canonical" href="https://1aeo.com/blog/{SLUG}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{html.escape(TITLE)}">
  <meta property="og:description" content="Two doors open, SSH for you and the ORPort for Tor, no password that works over SSH, and a check from outside that the relay publishes only what you set.">
  <meta property="og:url" content="https://1aeo.com/blog/{SLUG}">
  <meta property="og:image" content="https://1aeo.com/blog/{CHART}">
  <meta property="og:site_name" content="1AEO">
  <meta name="twitter:card" content="summary_large_image">
  {css}
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{TITLE}",
    "datePublished": "2026-10-10",
    "dateModified": "2026-10-10",
    "author": {{"@type": "Organization", "name": "1AEO"}},
    "publisher": {{"@type": "Organization", "name": "1AEO"}},
    "image": "https://1aeo.com/blog/{CHART}",
    "mainEntityOfPage": "https://1aeo.com/blog/{SLUG}",
    "description": "{DESC}"
  }}
  </script>
</head>
<body>
{nav}
  <div class="container">
    <!--email_off-->
    <h1>{TITLE}</h1>
    <p class="meta"><em>By 1AEO Team &bull; Published October 10, 2026 &bull; A non-exit relay on Ubuntu 24.04 or 26.04 LTS</em></p>

    <p class="series"><strong>Part 1 of a two-part series</strong> on securing Tor relay hosts after the October 2026 intrusions. &nbsp;1.&nbsp;<strong>Securing a Fresh Ubuntu VM for a Tor Relay</strong> (you are here) &mdash; one non-exit relay. &nbsp;2.&nbsp;{PART2_HTML} &mdash; several relays, offline keys, monitoring, incident response.</p>

    <div class="callout">
      <p><strong>Short answer:</strong> open exactly two doors, SSH for you (keys only, never a password) and the ORPort for Tor, then check from outside that the relay publishes only what you set. Five steps, about 30 minutes:</p>
      <ol>
        <li><a href="#prepare">Prepare</a>: unique passwords, an SSH key, Ubuntu's official image</li>
        <li><a href="#ssh">Lock SSH to keys</a>: an admin user, no passwords over SSH</li>
        <li><a href="#firewall">Open two ports</a>: SSH and Tor, nothing else</li>
        <li><a href="#tor">Install Tor from the Tor Project</a>: updated automatically</li>
        <li><a href="#check">Prove it, then check monthly</a>: from outside, plus a quick Ebury check</li>
      </ol>
    </div>

{body}
    <!--/email_off-->
    <p style="text-align: center;"><a href="/#get-involved" class="btn">Join the Mission</a></p>

    <div class="footer">
      <p>© 2026 1st Amendment Encrypted Openness | Privacy First | No Logs | No Borders</p>
    </div>
  </div>
</body>
</html>
"""
open(OUT, "w").write(page)
print("wrote", OUT, len(page))
