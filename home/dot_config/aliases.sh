#!/bin/bash

#################################
#  Shell Aliases and Functions  #
#################################

# shellcheck disable=SC1010
# shellcheck disable=SC2009
# shellcheck disable=SC2029
# shellcheck disable=SC2079
# shellcheck disable=SC2142
# shellcheck disable=SC2154
# shellcheck disable=SC2230

# ---------- cookie Aliases / Functions ----------
# def marker: COOKIE
alias ainit='cookie template.awk -D awk -x'
alias Binit='cookie full.sh -x'
alias binit='cookie minimal.sh -x'
cinit() { PROJECT="$1" cookie -f -t c.mk Makefile && cookie -f -t main.c src/main.c && cookie -f -t gtest.mk tests/Makefile && cookie -f -t main.gtest tests/main.cc; }
alias co='cookie'
hw() { mkdir -p HW"$1"/img &>/dev/null && ASSIGNMENT_NUMBER="$1" cookie hw.tex -f "${@:2}" HW"$1"/hw"$1".tex; }
alias minit='cookie c.make -f Makefile'
alias mtinit='cookie gtest.make -f Makefile'
pytinit() { SCRIPT="$1" cookie pytest_script.py -f test_"$1".py; }
robinit() { DATE="$(date +%Y%m%d)" cookie robot.yaml -f "$HOME"/.local/share/red_robot/pending/"$1"; }
alias texinit='cookie template.tex -f'
alias xinit='cookie template.exp -x'

# ---------- GTD Aliases / Functions ----------
# def marker: GTD
ka() { "$HOME"/.local/bin/ka "$@" && krestart_alarms; }
kc() { clear && khal calendar --notstarted --format '{start-time} {title} [{location}]' now && echo; }
ke() { khal edit "$@" && krestart_alarms; }
ki() { ikhal "$@" && krestart_alarms; }
alias knh='khal new -a home'
krestart_alarms() { setsid calalrms -d &>/dev/null; }
alias ta='task add'
tas() { tmux send-keys "ta project:Study.$*" "Enter"; }
tc() { clear && task next rc.verbose=blank,label rc.defaultwidth:$COLUMNS +READY limit:page; }
tcd() { task done "$1" && tc; }
alias tcn='task context none && task_refresh -F rename,config'
alias tcomp='task limit:10 \( status:completed or status:deleted \) rc.report.all.sort:end- all'
tcs() { task rc.context="$1" "${@:2}"; }
tcsn() { tcs none "$@"; }
tcx() { task context "$@" && task_refresh -F rename,config; }
alias td='task done'
alias tdel='task delete'
tdi() { task "$(tnext_inbox_id)" done; }
alias tdue='tga +OVERDUE'
tga() { eval "tcsn rc.verbose=blank,label rc.defaultwidth:$COLUMNS $* -COMPLETED -DELETED all"; }
tget() { task _get "$@"; }
tgp() { eval "tga project:$*"; }
tgps() { eval "tgp Study.$*"; }
tgs() { tga project:Study."$*"; }
tgw() { eval "tcsn $* rc.verbose=blank,label waiting"; }
ti() { task rc._forcecolor:on "$@" info | less; }
tin() { task rc.context=none +inbox -DELETED -COMPLETED all; }
tl() { task "$1" | less; }
alias tlat='task rc._forcecolor:on +LATEST info | less'
tnall() { tcsn "next +READY"; }
tnl() { task next +READY limit:none; } # no limit
tpa() { tga project:"$(tproject)"; }
trev() { task rc.context:review rc.verbose:nothing rc.defaultwidth:$COLUMNS limit:none \( +PENDING or +WAITING \) | less; }
alias tstudy='vim ~/.vimwiki/TaskWarrior.wiki'
tsub() { task "$1" modify "/$2/$3/g"; }
alias tw='timew'
alias wdel='if ! watson_is_on; then watson remove -f $(watson frames | tail -n 1); else return 1; fi'
alias wedit='watson edit'
alias wlog='watson log'
alias wstat='watson status'

# ---------- Mutt Aliases / Functions ----------
# def marker: MUTT
alias bmutt='neomutt -f /home/bryan/.mail'
alias mutt="neomutt"
alias sudo-mutt='sudo neomutt -f /var/spool/mail/root'
alias vmutt='vim $HOME/.mutt/muttrc'

# ---------- Vim Wrapper Aliases / Functions ----------
# def marker: VIM
cim() { vim ~/.config/"$1"; }
alias daf='def -a'
def() { zim "def" "$@" "-F" "$HOME/.zshrc" "-F" "$HOME/.config/aliases.sh" "-F" "$HOME/.config/debian.sh" "-F" "$HOME/.config/gentoo.sh" "-F" "$HOME/.config/macos.sh"; }
alias hh='helphelp'
him() { vim ~/"$1"; }
lim() { vim ~/.local/share/"$1"; }
mim() { zim "mim" "$@"; }
tam() {
  N="$(history -n | tail -n 100 | tac | nl | fzf --tiebreak=index | awk '{print $1}')"
  if [[ -n "${N}" ]]; then tim "${N}" "$@"; fi
}
tim() {
  f=$(fc -e - -"${1:-1}" 2>/dev/null | fzf -q "$2")
  if [[ -n "${f}" ]]; then vim "${f}"; fi
}
V() {
  find . -type f -not -path '*/*-venv/*' -not -path '*/*.egg-info/*' -not -path '*/.eggs/*' -not -path '*/.mypy_cache/*' -not -path '*/.pytest_cache/*' -not -path '*/.tox/*' -not -path '*/.venv/*' -not -path '*/build/*' -not -path '*/tmp/*' -not -path '*/venv/*' -not -path '*/.aider.chat.history.md' \( -name "*.ambr" -o -name "*.g4" -o -name "*.z*" -o -name "*.zot" -o -name "*.sh" -o -name "*.txt" -o -name "tox.ini" -o -name '*.cfg' -o -name '*.in' -o -name '*.json' -o -name '*.md' -o -name '*.mk' -o -name '*.py' -o -name '*.toml' -o -name '*.yaml' -o -name '*.yml' -o -name '*.rst' -o -name '*.uml' -o -name '*.txt' -o -name '*.pkgcfg' -o -name 'Dockerfile*' -o -name 'Jenkinsfile*' -o -name 'Makefile*' -o -name '*.j2' -o -path '*/bin/*' -o -path '*/scripts/*' \) -print | sort
}
alias v='nvim'
vs() { v -c "lua= vim.cmd('SessionRestore ' .. require('util').get_default_session_name())"; }
vv() { v $(V 2>/dev/null) "$@"; }
alias wam='wim -a'
wim() { zim wim "$@"; }
zim() { "$HOME"/.local/bin/zim "$@" || {
  EC="$?"
  if [[ "${EC}" -eq 3 ]]; then so; else return "${EC}"; fi
}; }

# ---------- File Copy / Cut / Paste ----------
p() { echo "The following files have been pasted into ${PWD}/${1}:" && ls -A /tmp/copy && /bin/mv -i /tmp/copy/* "${PWD}"/"${1}"; }
x() {
  mkdir /tmp/copy &>/dev/null
  /bin/mv "$@" /tmp/copy/
}
y() {
  mkdir /tmp/copy &>/dev/null
  /bin/cp -r "$@" /tmp/copy/
}

# ---------- Salary ----------
daily_salary() { printf "%f\n" $(($(weekly_salary "$1") / 5.0)); }
hourly_salary() { printf "%f\n" $(($(weekly_salary "$1") / 40.0)); }
hsal() { sal "$(($1 * 40.0 * 52.0 / 1000.0))" "${@:2}"; }
monthly_salary() { printf "%f\n" $(($(yearly_salary "$1") / 12.0)); }
DEFAULT_TAX_P=0.37 # Default tax percentage used for salary calculation.
NET_P=$((1.0 - DEFAULT_TAX_P))
sal() { clear && salary "$@" && echo; }
salary() { printf "======= BEFORE TAXES =======\n" && _salary "$1" 0 && printf "\n===== AFTER TAXES (%0.1f%%) =====\n" "${2:-$((DEFAULT_TAX_P * 100.0))}" && _salary "$@"; }
_salary() {
  { [[ -n "$2" ]] && NET_P=$((1.0 - ($2 / 100.0))); }
  printf "Hourly:       $%0.2f\nDaily:        $%0.2f\nWeekly:       $%0.2f\nBiweekly:     $%0.2f\nSemi-monthly: $%0.2f\nMonthly:      $%0.2f\nYearly:       $%0.2f\n" "$(hourly_salary "$1")" "$(daily_salary "$1")" "$(weekly_salary "$1")" "$((2 * $(weekly_salary "$1")))" "$((0.5 * $(monthly_salary "$1")))" "$(monthly_salary "$1")" "$(yearly_salary "$1")"
  NET_P=$((1.0 - DEFAULT_TAX_P))
}
weekly_salary() { printf "%f\n" $(($(yearly_salary "$1") / 52.0)); }
yearly_salary() { printf "%f\n" $(($1 * 1000.0 * NET_P)); }

# ---------- Miscellaneous Aliases / Functions ----------
# def marker: DEFAULT
alias activate='source venv/bin/activate'
addgroup() { sudo usermod -aG "$1" bryan; }
alias ag='ag --hidden'
alias anki='xspawn anki'
auto() {
  nohup autodemo "$@" &>/dev/null &
  disown && clear
}
bar() {
  i=0
  while [[ $i -lt "$1" ]]; do
    printf "*"
    i=$((i + 1))
  done
  printf "\n"
}
bb() { (
  source bb_proxies.sh
  "$@"
); }
alias bb_docker='docker --config /home/bryan/projects/work/bloomberg/.docker'
alias bb_pip_install='python -m pip install --index-url="http://artprod.dev.bloomberg.com/artifactory/api/pypi/bloomberg-pypi/simple" --proxy=192.168.1.198:8888 -U --trusted-host artprod.dev.bloomberg.com'
alias bbhub='bb GITHUB_TOKEN=$(pass show bbgithub\ Personal\ Access\ Token) hub'
alias bbs='PYTHONPATH=$PYTHONPATH:$(pysocks_site_packages) HTTPS_PROXY=socks5h://127.0.0.1:8080'
alias bbssh='command bbssh $(pass show bloomberg_ssh_password)'
alias bbtmp='scp -r "devnjbvlt01.bloomberg.com:/home/bbugyi/tmp/*" $HOME/projects/work/bloomberg/tmp/bb'
bc() { MASTER_BRANCH="${1:-"${MASTER_BRANCH:-master}"}" branch_changes; }
alias bcstat='git diff --stat $(git merge-base HEAD "${REVIEW_BASE:-master}")'
bgdb() { gdb "$1" -ex "b $2" -ex "run"; }
alias books='vim ~/Sync/var/notes/Journal/books.txt'
box() {
  blen=$((4 + ${#1}))
  bar "${blen}"
  printf "* %s *\n" "$1"
  bar "${blen}"
}
alias budget='python3 $HOME/Sync/var/projects/budget/main.py'
alias bw='sudo bandwhich'
alias c2m='clip2mac'
alias c3m='clip3mac'
alias c='cookie'
alias ccat='pygmentize -g'
ccd() { cd "$HOME/.cookiecutters/$1/{{ cookiecutter.project|lower }}" &>/dev/null || return 1; }
cd_sandbox() { # cd into sandbox directory based on today's date
  local sb_dir
  sb_dir="$(sandbox "$@")"
  local ec=$?
  if [[ "${ec}" -eq 0 ]]; then
    cd "${sb_dir}" && itree

    if [[ -d venv ]]; then
      source venv/bin/activate
      pip list
    fi
  else
    return "${ec}"
  fi
}
alias cdef='def -m COOKIE'
alias cdow='cd "$(dow_dir $PWD)"'
cdw() { cd "$@" && pyenv activate "$(get_venv_name)"; }
alias chez='chezmoi --no-pager'
cho() { sudo chown -R "${2:-bryan}":"${2:-bryan}" "$1"; }
alias chx='sudo chmod +x'
alias clip2hera='DISPLAY=:0 xclip -o -sel clip | tee /dev/stderr | hera DISPLAY=:0 xclip -sel clip'
alias clip2mac='xclip -o -sel clip | tee /dev/stderr | mac pbcopy'
alias clip3hera='hera DISPLAY=:0 xclip -o -sel clip | tee /dev/stderr | DISPLAY=:0 xclip -sel clip'
alias clip3mac='mac pbpaste | tee /dev/stderr | xclip -sel clip'
cmd_exists() { command -v "$1" &>/dev/null; }
alias cower='cower -c'
alias cp="cp -i"
alias cplug='vim +PlugClean +qall'
alias cppinit='cinit ++'
cprof() { python -m cProfile -s "$@" | less; }
cruftc() { rm -rf "$1" && cruft create "${@:2}" && cd "$1" || return 1; }
alias crun='cargo run --'
cval() {
  pushd "$1" &>/dev/null || return 1 && eval "$2"
  popd &>/dev/null || return 1
}
alias d.='desk .'
alias d='docker'
alias dayplan='cd $HOME/Sync/var/notes && vim dayplan.txt'
alias dc='docker-compose'
dci() { dc info --sort=time_added | awk -F ':' "{if(\$1==\"$1\")print \$0}"; }
alias ddef='def -m DEBIAN'
alias ddwrt-logs='sim /var/log/syslog-ddwrt'
alias del_swps='find . -name "*.swp" -delete -print'
alias delshots='confirm "find $HOME/Sync/var/aphrodite-motion -name \"*$(date +%Y%m%d)*\" -delete"'
alias dff='duf --only local'
dg() { {
  box "ALIAS DEFINITIONS"
  alias | grep --color=never -E "=.*$1" | grep --color=always -E "$1"
  printf "\n" && box "FUNCTION DEFINITIONS" && typeset -f | ${SED} '/^$/d' | ${SED} '/^_.\+ () {/,/^}$/d' | ${SED} 's/^}$/}\n/g' | grep --color=never -E " \(\) |$*" | ${SED} '/--$/d' | grep --color=never -B 1 -E "$1[^\(]*$" | grep --color=never --invert-match -E "$1.*\(\)" | grep -B 1 -E "$1" --color=never | ${SED} 's/ {$/:/g' | ${SED} '/--$/d' | ${SED} 'N;s/\:\n/: /g' | ${SED} 's/ ()\:\s*/(): /g' | grep -E "(): " | grep --color=always -E "$@"
  printf "\n"
  box "SCRIPT CONTENTS"
  rg -s -C 5 -p "$@" ~/Sync/bin
}; }
dgw() { dg "\W$1\W"; }
diff() { colordiff -wy -W "$(tput cols)" "$@" | less -R; }
alias dnd='do_not_disturb'
alias dst='dropbox-cli status'
alias dstart='dropbox-cli start'
alias dstop='dropbox-cli stop'
alias du='sudo ncdu --color dark'
alias dunst='killall dunst &> /dev/null; dunst'
alias edsl='printf "$(hostname):%d,%d\n%s,%d\n" $(emanage -D local -u) $(emanage -D local -c) $(emanage -D remote -u) $(emanage -D remote -c | perl -nE "print s/^.*://gr")'
alias epuse='sudo -E epuse'
_essh() { printf 'cd ~/projects/edgelp/prod; source envs/dev.sh; cd %s; /bin/zsh' "$1"; }
essh() { ssh "$1" -t "$(_essh "$2")"; }
esssh() { essh "$1" /prod/home/bbugyi/src/prod; }
alias farmd='farm -D'
alias farmh='farm -H'
farmpc() { farm -H $(farm bbhost -m "$1" | sort -u | head -n 1) "${@:2}"; }
farms() { (
  source bb_farm.sh
  bbsync "$@"
); }
alias farmsd='farms && farmd'
alias fav='fav_clips'
fim() {
  file="$("$(which -a fim | tail -n 1)" "$1")"
  if [[ -z "${file}" ]]; then return 1; else vim "${file}"; fi
}
alias flaggie='sudo -i flaggie'
alias fn='noglob fn_'
fn_() { if [[ "$1" == *"*"* ]]; then find . -iname "$@"; else find . -iname "*$**"; fi; }
forever() { while true; do eval "$*"; done; }
alias fp='noglob fp_'
fp_() { if [[ "$1" == *"*"* ]]; then find . -ipath "$@"; else find . -ipath "*$**"; fi; }
alias freeze='icebox --freeze /tmp/icebox'
alias ga='git add -v'
alias gaa='git add -v --all'
alias gau='git add -v --update'
alias gb='git brv'
alias gbb='git branch --sort=-committerdate | less'
alias gbcopy='gcopy --body'
gca() { if [[ -n "$1" ]]; then git commit -v -a -m "$1"; else git commit -v -a; fi; }
gcB() {
  gbD "$1" &>/dev/null
  git checkout -b "$1" "${2:-upstream}"/"$1"
}
gcbb() { git checkout -b CSRE-"$1" "${@:2}"; }
gcbc() { git checkout -b "$@" && git commit --allow-empty; }
gcbd() {
  if [[ -z "$1" ]]; then return 1; fi
  gcb "$(date +"%y.%m")"-"$1"
}
alias gce='git commit --allow-empty'
alias gcignore='git add .gitignore && git commit -m "Update: .gitignore file"'
gcl() { cd "$("$HOME"/bin/gcl "$@")" || return 1; }
gclbb() { cd "$(command gclbb "$@")" || return 1; }
gclog() { git commit -am "Update CHANGELOG for v$1"; }
gclp() { cd ~/projects/github && gcl "$@"; }
alias gclt='cd /tmp && gcl'
gcm() { git checkout "${MASTER_BRANCH:-master}"; }
gcopys() { gcopy --body "$@" &>/dev/null && gcopy --title "$@" &>/dev/null; }
alias gdef='def -m GENTOO'
alias Gdef='def -m GTD'
gdm() { git diff "$@" "${MASTER_BRANCH:-master}"...HEAD; }
alias gdo='git diff origin/master'
alias gdu='git diff | dunk'
alias geff='git effort'
alias gg='git pull'
alias gga='git rev-list --all | xargs git grep -n --break --heading'
alias gho='ghi open'
alias ghooks='rm -rf .git/hooks && git init'
alias gi='git info -c 3 --no-config'
alias ginit='while true; do; watch -d -n 1 cat .gdbinit; vim .gdbinit; done'
git() { if [[ -n "$1" ]]; then command git "$@"; else lazygit; fi; }
alias git_commit_cc='git commit -a -m "Sync repo with parent cookiecutter (i.e. run \`cruft update\`)"'
alias git_commit_pypi='git commit --allow-empty -m "[pypi] Publish dev version of this package to pypi"'
alias git_commit_reqs='git add requirements*.txt && git commit -m "Update requirements"'
git_issue_number() { git branch | grep '^\*' | awk '{print $2}' | awk -F'-' '{print $1}'; }
alias gl='git log'
alias glg++='glg ++'
alias glg+='glg +'
alias Glg='git log -p -G'
alias gmc='git ls-files -u | cut -f 2 | sort -u'
alias gnrld='FARM_HOST=gnrld-pw-885 REMOTE_HOME=/home/bbugyi farm'
gN() { git checkout HEAD~"${1:-1}"; }
gN1() { git_current_branch >/tmp/gnext-branch.txt && gN "$@"; }
alias gn='gnext'
alias gpa='git commit -v -a --no-edit --amend && git push --force'
alias gpf='git push --force'
alias gpr='PYTHONPATH=$PYTHONPATH:$(pysocks_site_packages) no_venv /home/bryan/.local/bin/github_pull_request -T $(pass show bbgithub\ Personal\ Access\ Token) -u bbugyi -x socks5h://127.0.0.1:8080'
alias gprm='gpup "Docs: Update README"'
gpu() { git push -u "${1:-origin}" "$(git_current_branch)"; }
alias gpull='git stash && git pull && git stash apply'
alias gra='git rebase --abort'
alias grc='git rebase --continue'
alias gre='git restore'
alias gres='git reset'
gresh() { git reset "${@:2}" HEAD~"${1:-1}"; }
greshh() { gresh "${1:-0}" --hard; }
greshs() { gresh "${1:-1}" --soft; }
alias grest='git restore'
alias grests='git restore --staged'
alias grl='git reflog'
alias grip='grip --user bbugyi200 --pass $(pass show github_personal_access_token)'
grun() { [[ "$(tail -n 1 "${PWD}"/.gdbinit)" == "r" ]] && sed -i '/^r$/d' "${PWD}"/.gdbinit || printf "r\n" >>"${PWD}"/.gdbinit; }
alias gsd='sudo get-shit-done'
alias gsta='git stash'
alias gstal="git stash list --date=local | perl -pE 's/stash@\{(?<date>.*)\}: .*[Oo]n (?<branch>.*?): (?<desc>.*)$/\"\\033[33mstash@\{\" . \$n++ . \"\}: \\033[36m[\$+{date}] \\033[32m(\$+{branch})\n\t\$+{desc}\n\"/ge' | less"
alias gsum='git summary | less'
alias gtcopy='gcopy --title'
alias gtd='greatday'
gwip() { gaa && git commit -m "[wip] $*"; }
alias h='tldr'
alias H='{ type deactivate && if ! deactivate &>/dev/null && cmd_exists pyenv; then pyenv deactivate &>/dev/null; fi  } >/dev/null; tm-home load'
header() { clear && eval "$@" && echo; }
help() { bash -c "help $*"; }
alias hera='ssh 192.168.0.3'
alias hlite='harlequin -a sqlite'
alias htime='hyperfine'
alias i='greatday add'
info() {
  pinfo "$@" || {
    printf "\n===== APROPOS OUTPUT =====\n"
    apropos "$@"
  }
}
alias iotop='sudo iotop'
alias ipdb='ipdb3'
alias iplug='vim +PlugInstall +qall'
alias ips='ip -brief addr'
ipy-add-import() { ${SED} -i "/c\.InteractiveShellApp\.exec_lines/ a import $1" ~/.ipython/profile_default/ipython_config.py; }
alias issh='ssh -p 34857 athena-arch.ddns.net'
ivim() { while true; do vim "$@" && sleep 0.5; done; }
ivimbc() { while true; do vim $(branch_changes | sort_by_basename | perl -nE 'print if not /thirdparty/') && sleep 0.5; done; }
alias j='jrnl'
alias J='pushd ~/Sync/var/notes/Journal &> /dev/null && ranger && popd &> /dev/null'
K() { tmux switchc -n && tmux kill-session -t "$(tm-session-name)"; }
alias k9='sudo kill -9'
Kman() { man -wK "$@" | awk -F'/' '{print $NF}' | sed 's/\.\(.*\)\.bz2$/ (\1)/g' | sort; }
alias kman='man -k'
alias lid='sudo libuser-lid'
alias loc='locate --regex'
alias Loc='sudo updatedb && loc'
alias lpass-login='lpass login bryanbugyi34@gmail.com'
alias l='clear && ls'
alias ll='clear && ls -a'
alias lll='clear && ls -a -l'
alias ls='exa -g'
alias lt='ls --tree'
m-torrent() { echo "torrent -w /media/bryan/hercules/media/Entertainment/Movies $*" | at 0200; }
alias mac='_mac bbremote'
alias _mac='REMOTE_HOST=bbmacbook REMOTE_HOME=/Users/bbugyi'
alias macd='mac -D'
alias macs='_mac bbsync'
alias macsd='macs && macd'
alias matlab='matlab -nojvm -nodisplay -nosplash'
alias merge_conflict_files='git diff --name-only --diff-filter=U'
alias mfood='macros food'
alias mirror='xrandr --output DVI-I-1-1 --auto --same-as LVDS1'
mkcd() { mkdir -p "$1" && cd "$1" || return 1; }
alias mkdir='mkdir'
alias mkgrub='sudo grub-mkconfig -o /boot/grub/grub.cfg'
alias mkpkg='makepkg -si'
alias mkpp='make_python_package'
alias mlog='macros log'
mov() { tman add -w "${MOV}" "${1:-"$(xclip -selection clipboard -out)"}"; }
alias mpvlc='xspawn -w mpv mpvlc'
alias mrun='macrun'
alias multivisor-cli='multivisor-cli --url athena:8100'
alias mv="mv -i"
alias myip='ip addr | grep -P -o "192.168.[01].[0-9]+" | grep -v -P "192.168.[01].255"'
new_home() { pushd ~/Sync/var/notes/homes &>/dev/null && ./new_home "$@" && popd &>/dev/null || return 1; }
no_venv() { # Wraps a command that will fail if a virtualenv is currently activated.
  old_venv="${VIRTUAL_ENV}"
  if [[ "${old_venv}" == *".pyenv"* ]]; then
    pyenv deactivate
  elif [[ -n "${old_venv}" ]]; then
    deactivate
  fi

  eval "$@"

  if [[ -n "${old_venv}" ]]; then
    source "${old_venv}"/bin/activate
  fi
}
alias noeye='eye --purge-eye'
alias nomirror='xrandr --output DVI-I-1-1 --auto --right-of LVDS1'
alias notes='pushd ~/Sync/var/notes/Journal &> /dev/null && ranger && popd &> /dev/null'
no_proxy() { (
  http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= "$@"
); }
alias ok='xspawn okular'
onething() { vim -c "/$(date --date="yesterday" +%m\\/%d\\/%Y)" ~/Sync/var/notes/Onething/"$1".txt; }
alias P='popd'
pdb() { { [[ -f ./"$1" ]] && python -m pdb "$@"; } || python -m pdb "$(which -a "$1" | tail -n 1)" "${@:2}"; }
pgr() { pgrep -f ".*$1.*"; }
pip() { "$(get_python_exe)" -m pip "$@"; }
alias pipget='pip install --user'
alias pj='vim + ~/Sync/var/notes/Journal/projects.txt'
alias plex='xspawn -w plex plexmediaplayer'
pname() { pass show | grep -i "$1" | awk '{print $2}'; }
ppg() { if [[ -n "$1" ]]; then pipenv graph | grep "$@"; else pipenv graph; fi; }
alias ppi2='pipenv --two install'
alias ppi='pipenv install'
alias ppr='pipenv run'
alias ppu='pipenv uninstall'
ppython() { pipenv run python "$@"; }
alias prun='poetry run'
alias psg='ps -aux | grep -v grep | grep'
alias pshell='poetry shell'
alias psi='psinfo'
alias pstrace="strace \$@ -p \$(ps -ax | fzf | awk '{print \$2}')"
pudb() { { [[ -f ./"$1" ]] && pudb3 "$@"; } || pudb3 "$(which -a "$1" | tail -n 1)" "${@:2}"; }
pvar() { set | grep -i -e "^$1"; }
alias pvsu='py-vshlog -u -D BOT EOT -H all -e'
alias pwrstat='sudo pwrstat'
pycov() { coverage run "$1" && coverage html && qutebrowser htmlcov/index.html; }
alias pyfix='run_python_fixers'
alias Q='tm-kill'
alias q='{ sleep 0.1 && cmd_exists tm-fix-layout && tm-fix-layout; } & disown && exit'
alias rag='cat $RECENTLY_EDITED_FILES_LOG | sudo xargs ag 2> /dev/null'
alias reboot='sudo reboot'
rgn() { rgna -g '!*_done*' -g '!*snippets*' -g '!*.git*' "$@"; }
rgna() { rg "$@" ~/org; }
rgz() { rg "$@" ~/org/**/*.zo; }
alias r='/bin/rm'
alias rm='trash'
alias rrm='r'
alias rng='ranger'
alias root='sudo su -p'
alias rrg='cat "$RECENTLY_EDITED_FILES_LOG" | sudo xargs rg 2> /dev/null'
alias sat='sudo cat'
alias sc='sudo systemctl'
alias sch='vim ~/Sync/var/notes/Rutgers/course_schedule.txt'
scp2mac() {
  D="$1"
  shift
  scp "$D" bbmacbook:/Users/bbugyi/"${1:-$D}"
}
scp3farm() { scp devnjbvlt01.bloomberg.com:/home/bbugyi/"$1" "$2"; }
scp3mac() { scp bbmacbook:/Users/bbugyi/"$1" "$2"; }
alias scu='systemctl --user'
alias sftp-rutgers='sftp bmb181@less.cs.rutgers.edu'
alias sim='sudo -E vim'
alias snapshots='find $HOME/Sync/var/aphrodite-motion -name "*$(date +%Y%m%d)*" | sort | xargs imv && delshots'
alias sos='sync_or_swim'
alias sqlite3='rlwrap -a -N -c -i sqlite3'
SS() { tmux send-keys "sleep 1.5 && !-2" "Enter"; }
alias ssh-aphrodite='ssh 192.168.1.193'
alias ssh-artemis="ssh bryan@67.207.92.152"
alias ssh-athena-tm='ssh-athena /home/bryan/.local/bin/tm Terminal'
ssh-rutgers() { ssh bmb181@"${1:-less}".cs.rutgers.edu; }
alias su='su -p'
alias sudo='sudo -E ' # makes aliases visible to sudo
alias sudoers='sudo -E vim /etc/sudoers'
alias supctl='supervisorctl -c /home/bryan/.config/supervisor/supervisord.conf'
alias tcpdump='sudo tcpdump'
alias tdp='toggle_docker_proxy'
tfm() {
  tm "$@"
  fg
}
alias tfpp='tmux capture-pane -p | fpp'
alias tgdb="gdb -iex 'set pagination off' -ex 'tui enable' -ex 'set pagination on'"
alias tm-layout="tmux lsw | grep '*' | awk '{gsub(/\\]/, \"\"); print \$7}'"
tmd() { tmux display-message -p "#{$1}"; }
alias todo='rg "^[ ]*..?[ ]TODO\(b?bugyi\):[ ].*$" -l --color=never | sort_by_basename | pytodos'
tqm() {
  tm "$@"
  q
}
tsm-add() { transmission-remote -a "$@"; }
tsm-boost() { transmission-remote -t"$1" -Bh -phall -pr250; }
tsm-mov() { tsm-add "${@:-$(xclip -sel clip -o)}" -w "$MOV"; }
tsm-purge() { transmission-remote -t"$1" -rad; }
tsm-rm() { transmission-remote -t"$1" -r; }
tsm-start() { sudo service transmission-daemon start; }
tsm-stop() { sudo service transmission-daemon stop; }
tsm-tv() { tsm-add "${@:-$(xclip -sel clip -o)}" -w "$TV"; }
tsm-watch() { watch -n "${1:-1}" tsm-status; }
alias tsm='transmission-remote'
alias turl='tmux capture-pane -p | urlview'
tv() { tman add -w "${TV}" "${1:-"$(xclip -selection clipboard -out)"}"; }
u() { echo -e "\u$1"; }
alias undow='dow --undo'
alias unfreeze='icebox --unfreeze /tmp/icebox'
alias updatedb='sudo updatedb'
alias uplug='vim +PlugUpdate +qall'
alias va='vv_push $HOME/projects/ansible_config'
vab() { vim $(find "$HOME"/Sync/bin/cron.jobs -type f | sort | tr '\n' ' '); }
alias valg='valgrind --leak-check=full --show-reachable=yes --track-origins=yes'
alias vapt='vim /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/preferences'
alias vb='vv_push $HOME/projects/pylibs'
alias vbb='vv_push $HOME/projects/bashlibs'
alias vbox='xspawn sudo virtualbox'
alias vbt='vim ~/.local/share/torrent/*.txt'
alias vbudget='pushd ~/projects/budget &>/dev/null && vim main.py && popd &>/dev/null'
alias vcron='vim ~/Sync/bin/cron.jobs/jobs.sh ~/Sync/bin/cron.jobs/{cron.hourly/hourly_jobs,cron.daily/daily_jobs,cron.weekly/weekly_jobs} ~/Sync/bin/cron.jobs/backup.sh ~/Sync/bin/cron.jobs/cron.{hourly,daily,weekly,monthly}/*'
alias vdaily="vgtd-daily-review"
alias vdb='vim $HOME/Sync/bin/cron/cron.daily/*'
alias vdiff='vimdiff -n'
venv() { vim "$HOME"/.zprofile "$HOME"/.profile "$HOME"/Sync/etc/environment "$(find "$HOME"/Sync/etc/profile.d -type f)" "$HOME"/.local/bin/etc-generator; }
alias vgdb-l='voltron view command "cmds set listsize $(tput lines) ; list *\$pc" --lexer c'
alias vgdb='vim ~/.gdbinit .gdbinit'
Vgi() { if [[ -f ./.local_gitignore ]]; then vim -c 'vs ./.local_gitignore' ~/.gitignore_global; else vim ~/.gitignore_global; fi; }
alias vgutils='vim /usr/bin/gutils.sh'
alias vihor='vim ~/Sync/var/notes/Horizons_of_Focus/*'
vimbc() { vim $(bc "$1"); }
alias vimilla='vim -u ~/.vanilla-vimrc'
vimmc() { vim $(merge_conflict_files); }
vimo() {
  if [[ -n "$1" ]]; then
    local name="$1"
    shift
  else
    local name="default"
  fi
  vim $(cat ~/var/vimo/"${name}".txt | ${SED} -n 's/^.*"\(.*\)"\s.*$/\1/p') "$@"
}
vimx() {
  local temp_file="$(mktemp --suffix='.clip.txt')"
  xclip -sel clip -out >"${temp_file}"
  vim "${temp_file}"
}
alias vipy='vim -c "/c.InteractiveShellApp.exec_lines" ~/.ipython/profile_default/ipython_config.py'
alias vmb='vim $HOME/Sync/bin/cron/cron.monthly/*'
alias vmkrules='make -p > /tmp/make-rules && vim /tmp/make-rules'
alias vnc-athena='open vnc://athena-arch.ddns.net:34590'
alias vnix='vv_push ~/.nixnote'
alias vpyutils='pushd ~/Sync/lib/python/gutils &> /dev/null && vv && popd &> /dev/null'
alias vq='vv_push ~/.config/qutebrowser'
alias vr='vim ${RECENTLY_EDITED_FILES_LOG}'
alias vrf='vv_push ~/Sync/bin/main/rfuncs'
vrobot() { vim "$HOME"/.local/share/red_robot/pending/"$1"; }
alias vs='vshlog'
alias vscratch='vim ~/Sync/var/notes/scratch.txt'
alias vsd='vshlog -H all -D'
alias vstudy='vim $HOME/.vimwiki/TaskWarrior.wiki'
alias vsup='vim /etc/supervisor/supervisord.conf ~/.config/supervisor/supervisord.conf ~/.config/supervisor/*'
alias vtorr='cval "$HOME/Sync/bin/main" "vim torrent libtorrent/**/[^_]*.py"'
alias vtv="vim \$HOME/.local/bin/tmux_view.sh \$HOME/.local/bin/tv_*"
vuse() { vim /etc/portage/package.use/"$1"; }
vv_push() { tmux send-keys "clear && pushd '$1' &> /dev/null && vv && popd &> /dev/null && clear" "Enter"; }
alias vwb='vim $HOME/Sync/bin/cron/cron.weekly/*'
alias vweekly='vgtd-weekly-review'
alias vx='vv_push ~/.xmonad'
alias vxorg='sudo -E vim /etc/X11/xorg.conf.d/*'
alias w-='pyenv deactivate'
alias w.='pyenv activate $(get_venv_name)'
alias w='which'
alias watdst='watch -n 5 dropbox-cli status'
alias wcut='watson stop && wedit && watson restart'
wdiff() { /usr/bin/wdiff -n -w "$(
  tput bold
  tput setaf 1
)" -x "$(tput sgr0)" -y "$(tput setaf 2)" -z "$(tput sgr0)" "$@" | less -R; }
alias wj='vim + ~/Sync/var/notes/Journal/work_jrnl.txt'
alias wkill='wtoggle && wdel'
alias wm='wmctrl'
alias wma='wmctrl -a'
alias wml='wmctrl -lx'
alias wrep='watson report -w'
alias wsensors='watch -n 1 sensors -f'
alias wttr='clear && curl "wttr.in/?T"'
alias wwat='watch -n 1 "{ wpoll; echo; watson log; }"'
alias xc='tee /dev/stderr | xclip -sel clipboard'
xco() { xclip -o -sel clipboard; }
alias xc_commit='git log -1 --format=%H | xc'
alias xdokey='xev -event keyboard'
alias xk='xdokey'
alias xmonad-keycodes='vim /usr/include/X11/keysymdef.h'
alias xs='xspawn'
yaml_to_json() { python -c 'import sys, yaml, json; json.dump(yaml.safe_load(sys.stdin), sys.stdout, indent=2)' <"$1"; }
ytd() {
  if [[ -z "$1" ]]; then
    printf 1>&2 "usage: ytd TITLE [URL]\n"
    return 2
  fi

  local title="yt_$1"
  shift

  if [[ "$(uname)" == "Darwin" ]]; then
    GET_CLIP="pbpaste"
    NOTIFY="terminal-notifier -title 'shell::zsh | function::ytd()' -message"
  else
    GET_CLIP="xclip -sel clipboard -out"
    NOTIFY="notify-send -t 0 'shell::zsh | function::ytd()'"
  fi

  if [[ -n "$1" ]]; then
    local url="$1"
    shift
  else
    local url="$($GET_CLIP)"
  fi

  pushd ~/org/videos &>/dev/null || return 1
  if yt-dlp --format "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" "${url}" --output "${title}"; then
    $NOTIFY "DOWNLOAD COMPLETE: ${ofile}"
  fi
  popd &>/dev/null || return 1
}
alias zath='xspawn zathura && xdotool key super+f'
alias zo='zorg'
alias zoc='zorg compile'
alias zomv='zorg file rename'
alias zoq='zorg query'
alias zot='zorg template'
alias zp='zpriority'

# ---------- bb_mkvirtualenv() and bb_sync_venv() definitions ----------
# public variables
PRIVATE_PYPACKS=(
  "birdseye"
  "devtools[pygments]"
  "ipython"
  "pip"
  "pip-tools"
  "pytest-cases" # added to fix 'black' virtualenv
  "pytest-cov"
  "pytest-pudb"
  "pytest-xdist"
  "snoop"
)
EDITABLE_PRIVATE_PYPACKS=(
  "${HOME}/projects/pudb"
  "${HOME}/projects/jedi"
)

# private variables
_FIRST_BB_HEADER=true

# Wrapper for virtualenvwrapper's mkvirtualenv().
function bb_mkvirtualenv() {
  _FIRST_BB_HEADER=true

  local package_name="$(get_venv_name)"
  local usage_msg="usage: bb_mkvirtualenv [-e ETARGET] [-r REQFILE] PYTHON_VERSION"

  if [[ "$1" == "-e" ]]; then
    shift

    if [[ -z "$1" ]]; then
      printf 1>&2 "%s\n" "${usage_msg}"
      return 1
    fi

    local etarget="$1"
    shift
  else
    local etarget="."
  fi

  if [[ "$1" == "-r" ]]; then
    shift

    if [[ -z "$1" ]]; then
      printf 1>&2 "%s\n" "${usage_msg}"
      return 2
    fi

    local reqfile="$1"
    shift

    if ! [[ -f "${reqfile}" ]]; then
      printf 1>&2 "The requirements file specified by the -r option does not exist: %s\n" "${reqfile}"
      return 1
    fi
  elif [[ -f requirements-dev.txt ]]; then
    local reqfile=requirements-dev.txt
  elif [[ -f dev-requirements.txt ]]; then
    local reqfile=dev-requirements.txt
  elif [[ -f requirements.txt ]]; then
    local reqfile=requirements.txt
  fi

  if [[ -z "$1" ]]; then
    printf 1>&2 "%s\n" "${usage_msg}"
    return 2
  fi
  local pyversion="$1"
  shift

  _bb_header "Creating new venv..."
  if cmd_exists pyenv && [[ -d $(pyenv root)/plugins/pyenv-virtualenv ]]; then
    if ! pyenv virtualenv "${pyversion}" "${package_name}"; then
      printf 1>&2 "The 'pyenv virtualenv ${pyversion} ${package_name}' command failed.\n"
      return 1
    fi

    if ! pyenv activate "${package_name}"; then
      printf 1>&2 "The 'pyenv activate ${package_name}' command failed.\n"
      return 1
    fi

    if [[ -n "${WORK_DIR}" ]]; then
      local work_venv="${WORK_DIR}/.virtualenvs/${package_name}"
      local work_venv_dir="$(dirname "${work_venv}")"
      [[ -d "${work_venv_dir}" ]] || mkdir -p "${work_venv_dir}"

      _bb_imsg "Moving venv directory from ${VIRTUAL_ENV} to ${work_venv}..."

      mv "${VIRTUAL_ENV}" "${work_venv}"
      ln -s "${work_venv}" "${VIRTUAL_ENV}"
    fi
  elif ! mkvirtualenv "$@" "${package_name}"; then
    printf 1>&2 "The mkvirtualenv command failed.\n"
    return 1
  fi

  if [[ -n "${reqfile}" ]]; then
    echo "${reqfile}" >"${VIRTUAL_ENV}"/.reqfile

    _bb_header "Installing pacakges listed in requirements file: %s" "${reqfile}"
    pip install -U -r "${reqfile}"
  else
    _bb_imsg "No requirements file found. Skipping installation of requirements file packages."
  fi

  # _setup_sitecustomize

  _update_private_packs

  if [[ -f setup.py ]]; then
    _bb_header "Installing the '%s' package in development mode..." "${package_name}"
    echo "${etarget}" >"${VIRTUAL_ENV}"/.etarget
    pip install -e "${etarget}"
  else
    _bb_imsg "No setup.py file found. Skipping '%s' package install." "${package_name}"
  fi
}

# Sync a virtualenv which was created using bb_mkvirtualenv().
function bb_sync_venv() {
  _FIRST_BB_HEADER=true

  local package_name="$(get_venv_name)"
  if [[ -z "${VIRTUAL_ENV}" ]]; then
    if pyenv activate "${package_name}"; then
      _bb_imsg "Sourcing the '%s' virtual environment..." "${package_name}"
    else
      printf 1>&2 "The bb_sync_venv() function can only be called AFTER a virtual environment has already been activated OR when inside of a directory where \`workon .\` works.\n"
      return 1
    fi
  fi

  # _setup_sitecustomize

  local reqfile_file="${VIRTUAL_ENV}"/.reqfile
  if [[ -f "${reqfile_file}" ]]; then
    local reqfile="$(cat "${reqfile_file}")"

    if ! [[ -f "${reqfile}" ]]; then
      printf 1>&2 "The requirements file listed in %s does not exist: %s\n" "${reqfile_file}" "${reqfile}"
      return 1
    fi

    _bb_header "Syncing packages listed in requirements file: %s" "${reqfile}"
    python3 -m piptools sync "${reqfile}"
  else
    _bb_imsg "No requirements file found. Skipping requirements file sync."
  fi

  _update_private_packs

  if [[ -f setup.py ]]; then
    local etarget_file="${VIRTUAL_ENV}"/.etarget
    if [[ -f "${etarget_file}" ]]; then
      local etarget="$(cat "${etarget_file}")"
    else
      local etarget="."
    fi
    _bb_header "Updating the '%s' package..." "${package_name}"
    pip install -e "${etarget}"
  else
    _bb_imsg "No setup.py file found. Skipping '%s' package update." "${package_name}"
  fi
}

function _bb_header() {
  if [[ "${_FIRST_BB_HEADER}" = true ]]; then
    _FIRST_BB_HEADER=false
  else
    printf "\n"
  fi

  printf ">>> %s\n" "$(printf "$@")"
}

function _bb_imsg() {
  _bb_header "$@"
  _FIRST_BB_HEADER=true
}

function _setup_sitecustomize() {
  _bb_imsg "Adding sitecustomize.py hooks..."

  local venv_lib="${VIRTUAL_ENV}"/lib/python"$(current_python_version)"
  echo "import os, sys; sys.path.insert(0, f\"{os.environ['VIRTUAL_ENV']}/lib/python{'.'.join(str(v) for v in sys.version_info[:2])}\")" >"${venv_lib}"/site-packages/sitecustomize.pth

  local sitecustomize_contents
  read -r -d '' sitecustomize_contents <<-EOM
try:
    from devtools import debug
except ImportError:
    pass
else:
    __builtins__['dprint'] = debug

try:
    from birdseye import eye
except ImportError:
    pass
else:
    __builtins__['eye'] = eye

try:
    from snoop import spy
except ImportError:
    pass
else:
    __builtins__['spy'] = spy
EOM

  echo "${sitecustomize_contents}" >"${venv_lib}"/sitecustomize.py
}

function _update_private_packs() {
  _bb_header "Installing / Updating private packaages: ${PRIVATE_PYPACKS[*]}"
  pip install -U "${PRIVATE_PYPACKS[@]}"

  _bb_header "Installing / Updating editable private packaages: ${EDITABLE_PRIVATE_PYPACKS[*]}"
  for epack in "${EDITABLE_PRIVATE_PYPACKS[@]}"; do
    if [[ -d "${epack}" ]]; then
      pip install -e "${epack}"
    fi
  done
}

### Source platform specific alias files.
function source_if_exists() { [[ -f "$1" ]] && source "$1"; }
sys_info="$(uname -a)"
if [[ "${sys_info}" == *"gentoo"* ]]; then
  source_if_exists "$HOME/.config/gentoo.sh"
elif [[ "${sys_info}" == *"Debian"* ]]; then
  source_if_exists "$HOME/.config/debian.sh"
elif [[ "${sys_info}" == *"Darwin"* ]]; then
  source_if_exists "$HOME/.config/macos.sh"
fi
