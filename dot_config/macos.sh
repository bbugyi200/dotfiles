# ---------- MacOS Aliases / Functions ----------
# def marker: MAC
alias chrome='/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome'
alias del='brew remove'
alias firefox='/Applications/Firefox.app/Contents/MacOS/firefox'
alias gco='git checkout'
alias gd='git diff'
alias gtd='greatday'
alias get='brew install'
alias get_python_exe='echo python3'
alias qutebrowser='/Users/bbugyi/.ansible/build/qutebrowser/.venv/bin/python -m qutebrowser -C ~/.config/qutebrowser/config.py'

# add pipx bin path to PATH envvar...
if command -v python3 &>/dev/null; then
    _pyver="$(python3 --version | perl -lanE 'print $F[1]' | perl -nE 'print s/([1-9]\.[1-9][0-9]*)\.[1-9][0-9]*/\1/gr')"
    export PATH="$HOME/Library/Python/${_pyver}/bin:$PATH"
fi
