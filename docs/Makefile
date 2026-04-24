PREFIX := /usr/local
DATADIR := ${PREFIX}/share
MANDIR := $(DATADIR)/man
GO ?= go
GOMD2MAN ?= go-md2man
ROOTDIR := $(abspath ..)
ifeq ($(shell uname -s),FreeBSD)
SED=gsed
else
SED=sed
endif
# This must never include the 'hack' directory
export PATH := $(shell $(GO) env GOPATH)/bin:$(PATH)
export GITIGNORE := $(shell tail -n +2 .gitignore)

MANPAGES_MD_IN := $(wildcard *.md.in)
MANPAGES_MD_GENERATED := $(MANPAGES_MD_IN:%.md.in=%.md)
MANPAGES_STAMP := .manpages-md.stamp

# Wildcard alone misses generated *.md not yet present at make parse time.
ALL_MD_SOURCES := $(sort $(MANPAGES_MD_GENERATED) $(wildcard *[157].md))
DOCS_MAN_TARGETS := $(patsubst %.md,%,$(ALL_MD_SOURCES))

docs: install-tools manpages-md $(DOCS_MAN_TARGETS)

%.1: %.1.md
### sed is used to filter http/s links as well as relative links
### replaces "\" at the end of a line with two spaces
### this ensures that manpages are rendered correctly
	@$(SED) -e 's/\((ramalama[^)]*\.md\(#.*\)\?)\)//g' \
	 -e 's/\[\(ramalama[^]]*\)\]/\1/g' \
	 -e 's/\[\([^]]*\)](http[^)]\+)/\1/g' \
	 -e 's;<\(/\)\?\(a\|a\s\+[^>]*\|sup\)>;;g' \
	 -e 's/\\$$/  /g' $<  | \
	$(GOMD2MAN) -in /dev/stdin -out  $@

%.5: %.5.md
### sed is used to filter http/s links as well as relative links
### replaces "\" at the end of a line with two spaces
### this ensures that manpages are rendered correctly
	@$(SED) -e 's/\((ramalama[^)]*\.md\(#.*\)\?)\)//g' \
	 -e 's/\[\(ramalama[^]]*\)\]/\1/g' \
	 -e 's/\[\([^]]*\)](http[^)]\+)/\1/g' \
	 -e 's;<\(/\)\?\(a\|a\s\+[^>]*\|sup\)>;;g' \
	 -e 's/\\$$/  /g' $<  | \
	$(GOMD2MAN) -in /dev/stdin -out  $@

%.7: %.7.md
### sed is used to filter http/s links as well as relative links
### replaces "\" at the end of a line with two spaces
### this ensures that manpages are rendered correctly
	@$(SED) -e 's/\((ramalama[^)]*\.md\(#.*\)\?)\)//g' \
	 -e 's/\[\(ramalama[^]]*\)\]/\1/g' \
	 -e 's/\[\([^]]*\)](http[^)]\+)/\1/g' \
	 -e 's;<\(/\)\?\(a\|a\s\+[^>]*\|sup\)>;;g' \
	 -e 's/\\$$/  /g' $<  | \
	$(GOMD2MAN) -in /dev/stdin -out  $@

# Run the preprocessor once (avoids parallel make rerunning it per .md and races
# when rewriting docs/options cross-reference headers).
$(MANPAGES_STAMP): $(MANPAGES_MD_IN) $(wildcard options/*.md) $(ROOTDIR)/hack/markdown-preprocess
	$(ROOTDIR)/hack/markdown-preprocess
	@touch $@

# go-md2man consumes these; depend on the stamp so they exist before parallel roff builds.
$(MANPAGES_MD_GENERATED): $(MANPAGES_STAMP)
	@test -f '$@'

.PHONY: manpages-md
manpages-md: $(MANPAGES_MD_GENERATED)

.PHONY: install
install: docs
	install -d ${DESTDIR}/${MANDIR}/man1
	install -m 0644 ramalama*.1 ${DESTDIR}/${MANDIR}/man1
	install -m 0644 links/ramalama*.1 ${DESTDIR}/${MANDIR}/man1
	install -d ${DESTDIR}/${MANDIR}/man5
	install -m 0644 ramalama*.5 ${DESTDIR}/${MANDIR}/man5
	install -d ${DESTDIR}/${MANDIR}/man7
	install -m 0644 ramalama*.7 ${DESTDIR}/${MANDIR}/man7

	install -d ${DESTDIR}/${DATADIR}/ramalama
	install -m 0644 ramalama.conf ${DESTDIR}/${DATADIR}/ramalama

.PHONY: install-tools
install-tools:
	@command -v $(GOMD2MAN) >/dev/null 2>&1 || $(GO) install github.com/cpuguy83/go-md2man@latest

.PHONY: clean
clean:
	$(RM) -f ramalama*.1 ramalama*.5 ramalama*.7
	$(RM) -f $(MANPAGES_MD_GENERATED) $(MANPAGES_STAMP)
