SED=sed
# The 'sort' below is crucial: without it, 'make docs' behaves differently
# on the first run than on subsequent ones, because the generated .md
MANPAGES_SOURCE_DIR = source/markdown
MANPAGES_MD ?= $(sort $(wildcard $(MANPAGES_SOURCE_DIR)/*.md))
MANPAGES ?= $(MANPAGES_MD:%.md=%)
MANPAGES_DEST ?= $(subst markdown,man, $(subst source,build,$(MANPAGES)))
$(MANPAGES): OUTFILE=$(subst source/markdown,build/man,$@)
$(MANPAGES): %: %.md
GOMD2MAN ?= /usr/bin/go-md2man
MANPAGES_DEST ?= $(subst markdown,man, $(subst source,build,$(MANPAGES)))
SELINUXOPT ?= $(shell test -x /usr/sbin/selinuxenabled && selinuxenabled && echo -Z)

.PHONY: docdir
docdir:
	mkdir -p build/man
$(MANPAGES): OUTFILE=$(subst source/markdown,build/man,$@)
$(MANPAGES): %: %.md  docdir
	@$(SED) -e 's/\((ramalama[^)]*\.md\(#.*\)\?)\)//g'    \
	       -e 's/\[\(ramalama[^]]*\)\]/\1/g'              \
	       -e 's/\[\([^]]*\)](http[^)]\+)/\1/g'         \
	       -e 's;<\(/\)\?\(a\|a\s\+[^>]*\|sup\)>;;g'    \
	       -e 's/\\$$/  /g' $<                         |\
	$(GOMD2MAN) -out $(OUTFILE)

.PHONY: install
install: $(MANPAGES)
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)$(MANDIR)/man1
	install ${SELINUXOPT} -m 644 $(filter %.1,$(MANPAGES_DEST)) $(DESTDIR)$(MANDIR)/man1

clean:
	$(RM) -fr build

