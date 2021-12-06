# ---------- MacOS Aliases / Functions ----------
# def marker: MAC
alias chrome='/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome'
alias del='brew remove'
alias firefox='/Applications/Firefox.app/Contents/MacOS/firefox'
alias get='brew install'
alias qutebrowser='/Applications/qutebrowser.app/Contents/MacOS/qutebrowser'

if command -v python3 &>/dev/null; then
    _pyver="$(python3 --version | perl -lanE 'print $F[1]' | perl -nE 'print s/([1-9]\.[1-9][0-9]*)\.[1-9][0-9]*/\1/gr')"
    export PATH="$HOME/Library/Python/${_pyver}/bin/pipx:$PATH"
fi
