PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib/amui
DATADIR ?= $(PREFIX)/share/amui
APPDIR ?= $(PREFIX)/share/applications

.PHONY: install uninstall check

check:
	python3 -m unittest discover -s tests -v

install:
	install -Dm644 lib/amui/features.py "$(DESTDIR)$(LIBDIR)/features.py"
	install -Dm644 share/amui/config.example.toml "$(DESTDIR)$(DATADIR)/config.example.toml"
	install -Dm755 bin/amui "$(DESTDIR)$(BINDIR)/amui"
	install -Dm755 bin/amui-kitty "$(DESTDIR)$(BINDIR)/amui-kitty"
	install -d "$(DESTDIR)$(APPDIR)"
	sed 's|@BINDIR@|$(BINDIR)|g' share/amui/amui.desktop.in > "$(DESTDIR)$(APPDIR)/amui.desktop"

uninstall:
	rm -f "$(DESTDIR)$(BINDIR)/amui"
	rm -f "$(DESTDIR)$(BINDIR)/amui-kitty" "$(DESTDIR)$(APPDIR)/amui.desktop"
	rm -f "$(DESTDIR)$(LIBDIR)/features.py" "$(DESTDIR)$(DATADIR)/config.example.toml"
