from are_my_clothes_dry.detector import CycleStarted, CycleStopped, DryerDetector

POLL_S = 10


def simulate(detector, *segments):
    """Feed (watts, duration_s) segments as readings POLL_S apart; return [(time, event)]."""
    events = []
    t = 0
    for watts, duration_s in segments:
        for _ in range(duration_s // POLL_S):
            event = detector.update(t, watts)
            if event is not None:
                events.append((t, event))
            t += POLL_S
    return events


def test_idle_dryer_never_notifies():
    assert simulate(DryerDetector(), (0.5, 3600)) == []


def test_full_cycle_starts_once_then_stops():
    events = simulate(DryerDetector(), (0, 60), (2000, 3600), (0.5, 120))
    # Run is announced on its first reading at t=60, stops at t=3660,
    # and is reported stopped after 20 s of idle.
    assert events == [(60, CycleStarted()), (3680, CycleStopped(3600))]


def test_brief_dip_does_not_stop_cycle():
    events = simulate(DryerDetector(), (2000, 600), (0.5, 20), (2000, 600), (0, 120))
    assert [type(e) for _, e in events] == [CycleStarted, CycleStopped]
    assert events[-1][1] == CycleStopped(1220)


def test_short_run_still_reports_stop():
    events = simulate(DryerDetector(), (0, 60), (300, 30), (0, 600))
    assert events == [(60, CycleStarted()), (110, CycleStopped(30))]


def test_exactly_threshold_counts_as_idle():
    assert simulate(DryerDetector(), (10, 3600)) == []
    events = simulate(DryerDetector(), (2000, 600), (10, 30))
    assert [type(e) for _, e in events] == [CycleStarted, CycleStopped]


def test_rearms_for_next_cycle():
    events = simulate(DryerDetector(), (2000, 1800), (0, 600), (2000, 1800), (0, 120))
    assert [type(e) for _, e in events] == [CycleStarted, CycleStopped, CycleStarted, CycleStopped]


def test_running_spans_start_to_stop():
    detector = DryerDetector()
    assert not detector.running
    detector.update(0, 2000)
    assert detector.running
    detector.update(10, 0)
    assert detector.running  # still inside the idle wait
    detector.update(30, 0)
    assert not detector.running
