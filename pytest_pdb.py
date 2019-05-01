from __future__ import print_function
import pdb
import pytest
import sys
import warnings


class PytestPdbUserWarning(UserWarning):
    pass


def _is_relevant_frame(frame):
    """
    Check given frame for a relevant pytest item.

    Returns pytest.Item on success, None otherwise.
    """
    for value in frame.f_locals.values():
        try:
            if isinstance(value, pytest.Item):
                return value
        except Exception:
            pass


def find_test_by_frame(currentframe):
    frame = currentframe
    prev = frame
    while frame:
        pytest_item = _is_relevant_frame(frame)
        if pytest_item:
            return (pytest_item, prev)
        prev = frame
        frame = frame.f_back
    return (None, currentframe)


def find_test_by_stack(stack):
    for index, (frame, lineno) in reversed(list(enumerate(stack))):
        pytest_item = _is_relevant_frame(frame)
        if pytest_item:
            return (pytest_item, stack[index + 1][0], index + 1)
    return (None, stack[0], 0)


def find_settrace_frame(curframe):
    frame = curframe
    while frame:
        if frame.f_code.co_name == 'set_trace':
            if frame.f_back:
                return frame.f_back
        frame = frame.f_back


def offset_between_frames(currentframe, destinationframe):
    # search from current
    index = 0
    frame = currentframe
    while frame:
        if frame == destinationframe:
            return index
        index -= 1
        frame = frame.f_back
    # search from destination
    index = 0
    frame = destinationframe
    while frame:
        if frame == currentframe:
            return index
        index += 1
        frame = frame.f_back


def offset_description(offset):
    if offset == 0:
        return 'at current frame'
    elif offset == 1:
        return '1 frame above'
    elif offset > 1:
        return '%s frames above' % offset
    elif offset == -1:
        return '1 frame below'
    else:
        return '%s frames below' % -offset


class PdbExtension:
    def do_whichtest(self, arg):
        """whichtest | wt
        Show which test we are currently in.
        """
        (test, frame, index) = find_test_by_stack(self.stack)
        if test is None:
            print("Couldn't determine current test", file=self.stdout)
            return

        offset = index - self.curindex

        print("Currently in {} ({}:{}) on line {} ({})".format(
            test.location[2], test.location[0], test.location[1] + 1,
            frame.f_lineno, offset_description(offset)), file=self.stdout)
    do_wt = do_whichtest

    def do_gototest(self, arg):
        """gototest | gt
        Go to frame containing the current test.
        """
        (test, frame, index) = find_test_by_stack(self.stack)
        if test is None:
            print("Couldn't determine current test.", file=self.stdout)
            return

        self._select_frame(index)
    do_gt = do_gototest

    def do_top(self, arg):
        """top
        Move to top (oldest) frame.
        """
        if self.curindex == 0:
            self.error('Oldest frame')
            return
        self._select_frame(0)

    def do_bottom(self, arg):
        """bottom
        Move to bottom (newest) frame.
        """
        if self.curindex + 1 == len(self.stack):
            self.error('Newest frame')
            return
        self._select_frame(len(self.stack) - 1)


def pytest_configure(config):
    cmds = {x[3:] for x in dir(PdbExtension) if x.startswith('do_')}

    prefixes = {'do', 'help'}
    for prefix in prefixes:
        for cmd in cmds:
            attr = '%s_%s' % (prefix, cmd)

            new = getattr(PdbExtension, attr, None)
            if new is None:
                continue

            if hasattr(pdb.Pdb, attr):
                existing = getattr(pdb.Pdb, attr)
                if existing is new:
                    # This might happen if the plugin is loaded multiple times,
                    # e.g. with pytest's own inline tests.
                    continue

                warnings.warn("{}.{}_{} exists already, skipping.".format(
                    pdb.Pdb, prefix, cmd), PytestPdbUserWarning)
                continue

            setattr(pdb.Pdb, attr, new)
