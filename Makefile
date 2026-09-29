PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib/amui
DATADIR ?= $(PREFIX)/share/amui

.PHONY: install uninstall check

check:
	python3 -m unittest discover -s tests -v

install:
	install -Dm644 lib/amui/features.py "$(DESTDIR)$(LIBDIR)/features.py"
	install -Dm644 share/amui/config.example.toml "$(DESTDIR)$(DATADIR)/config.example.toml"
	install -Dm755 bin/amui "$(DESTDIR)$(BINDIR)/amui"

uninstall:
	rm -f "$(DESTDIR)$(BINDIR)/amui"
	rm -f "$(DESTDIR)$(LIBDIR)/features.py" "$(DESTDIR)$(DATADIR)/config.example.toml"
