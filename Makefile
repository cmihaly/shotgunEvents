#!/usr/bin/env make
# The default target is...
all::

PYTHON ?= python
FLAVOR ?= optimize

# Guard against garbage on stdout from bad shells
VERSION ?= $(shell env TERM=dummy $(PYTHON) scripts/generate-version.py)

# Guard against CDPATH which breaks shell piplines
unexport CDPATH

prefix ?= $(shell pf-makevar root --absolute)
pfmakevar ?= pf-makevar --root=$(prefix) --absolute $(mac_flags)

bindir ?= $(DESTDIR)$(shell $(pfmakevar) bin)
pylibs ?= $(DESTDIR)$(shell $(pfmakevar) python-site)
share ?= $(DESTDIR)$(shell $(pfmakevar) share)
data ?= $(DESTDIR)$(shell $(pfmakevar) data shotgunEvents)
srcdata ?= $(shell pf-makevar data shotgunEvents)
rsync ?= rsync -ar --omit-dir-times --delete --exclude=.pythoscope --exclude='*.swp' --exclude='*~' --exclude tests
docsreldir = /share/WWW/htdocs/new/technology/software/products/shotgunEvents
docinstdir ?= $(DESTDIR)$(shell $(pfmakevar) doc shotgunEvents)
release_flags=

python_inc ?= $(shell pf-makevar python-inc)
python_ver ?= $(shell pf-makevar python-ver)

-include config.mak
# test flags can be specified on the command line for passing
# extra arguments to nose.  You can also add a 'config.mak'
# in this same directory to redefine these variables as needed.
all:: install

makevars:
	@(test -n "$(prefix)" && \
	  test -n "$(srcdata)" && \
	  test -n "$(pylibs)") || \
	(echo "error: undefined build variables: is pathfinder installed?"; \
	 false)

install: makevars  install-doc
	@mkdir -p $(pylibs)
	$(rsync) --exclude=tests src/shotgunEvents  $(pylibs)/

#	@mkdir -p $(bindir)
#	$(rsync) bin/pm* $(bindir)/

	find $(DESTDIR)$(prefix) -name '*.py[co]' -print0 | xargs -0 rm -f
	find $(DESTDIR)$(prefix) -name '*~' -print0 | xargs -0 rm -f
	$(PYTHON) -mcompileall -q $(DESTDIR)$(prefix)
	/bin/ls -1 $(DESTDIR)$(prefix) > .release.txt
	@echo
	@echo shotgunEvents version $(VERSION)

clean: makevars
	find . -name '*.py[co]' -print0 | xargs -0 rm -f
	find . -name .noseids -print0 | xargs -0 rm -f
	rm -f .cache
	rm -f src/shotgunEvents/_version.py*
	rm -fr $(pylibs)/shotgunEvents/
	rm -fr $(docinstdir)/* $(docinstdir)/.buildinfo
	rmdir -p $(docinstdir) || true
	rmdir -p $(pylibs) 2>/dev/null || true

pylint:
	@env PYTHONPATH="$(CURDIR)/src":"$(CURDIR)/lib":"$(PYTHONPATH)" \
        pylint --rcfile $(CURDIR)/.pylintrc -f parseable --disable=R0801,E1101,I0011,E0611 --ignore=tests, src  

release-docs:
	mkdir -p $(docsreldir)
	chmod -R 775 doc
	cd /docs && \
	make html && \
	chmod -R 775 _build/html && \
	$(rsync) _build/html/ $(docsreldir)/api/

install-doc:
	mkdir -p $(docinstdir)
	cd docs && \
	$(MAKE) html && \
	$(rsync) _build/html/ $(docinstdir)/

rpm:
	git make-rpm

cleanrpm:
	rm -rf /disk1/scratch/rpmbuild/RPMS/noarch/shotgunEvents-*
	rm -rf /disk1/scratch/rpmbuild/SRPMS/shotgunEvents-*
	rm -rf /disk1/scratch/rpmbuild/BUILD/shotgunEvents-*
	rm -rf /disk1/scratch/rpmbuild/BUILDROOT/shotgunEvents-*

release: release-docs install
	scripts/release -a Linux-x86_64:all -- $(release_flags)
	scripts/release -a Darwin:all -- $(release_flags)

.PHONY: test test-install clean coverage makevars rpm cleanrpm pkg
