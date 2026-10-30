import f1_search_frame as search


LAP_STARTS = [194.277, 270.787, 364.798]
OBSERVED_LAP_DIGIT_ROWS = {
    0: (
        "........",
        "........",
        "..####..",
        ".######.",
        ".##..##.",
        ".######.",
        ".###.##.",
        ".##..##.",
        ".######.",
        "..####..",
        "........",
        "........",
    ),
    1: (
        "........",
        "........",
        "..##....",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "..####..",
        "........",
        "........",
    ),
    2: (
        "........",
        "........",
        "..####..",
        "..#####.",
        "....###.",
        "...###..",
        "..###...",
        ".###....",
        ".#####..",
        "..####..",
        "........",
        "........",
    ),
    3: (
        "........",
        "........",
        "..####..",
        "..####..",
        "....##..",
        "..####..",
        "..####..",
        "....##..",
        "..####..",
        "..###...",
        "........",
        "........",
    ),
}


def observed_lap_digit_mask(digit):
    return search.digit_rows_to_mask(OBSERVED_LAP_DIGIT_ROWS[digit])


def test_lap_navigation_from_between_starts():
    assert search.next_lap_start(LAP_STARTS, 300, 0.008) == 364.798
    assert search.previous_lap_start(LAP_STARTS, 300, 0.008) == 270.787


def test_lap_navigation_on_a_start_steps_to_the_neighbour():
    assert search.next_lap_start(LAP_STARTS, 270.787, 0.008) == 364.798
    assert search.previous_lap_start(LAP_STARTS, 270.787, 0.008) == 194.277


def test_lap_navigation_stops_at_the_ends():
    assert search.previous_lap_start(LAP_STARTS, 0, 0.008) is None
    assert search.next_lap_start(LAP_STARTS, 364.798, 0.008) is None


def test_lap_digit_templates_match_themselves_and_stay_apart():
    masks = {digit: search.lap_digit_template(digit) for digit in (0, 1, 2, 3)}
    for digit, mask in masks.items():
        assert search.lap_digit_distance(mask, mask) == 0
        assert search.match_lap_digit(mask) == digit
    for left in range(4):
        for right in range(left + 1, 4):
            assert search.lap_digit_distance(masks[left], masks[right]) >= 11
    assert search.lap_digit_distance(masks[0], masks[1]) == 31
    assert search.lap_digit_distance(masks[2], masks[3]) == 11


def test_observed_lap_glyphs_match_their_digits():
    for digit in range(4):
        mask = observed_lap_digit_mask(digit)
        own_distance = search.lap_digit_distance(mask, search.lap_digit_template(digit))
        assert own_distance == 0
        assert search.match_lap_digit(mask) == digit
        for other in range(4):
            if other == digit:
                continue
            other_distance = search.lap_digit_distance(mask, search.lap_digit_template(other))
            assert other_distance >= own_distance + 4


def test_observed_glyph_plus_one_produces_a_lap_start():
    samples = []
    time_seconds = 10.0
    for digit in range(4):
        samples.append((time_seconds, search.match_lap_digit(observed_lap_digit_mask(digit))))
        time_seconds += 5.0
    brackets = search.lap_brackets_from_digits(samples)
    assert [bracket[2] for bracket in brackets] == [1, 2, 3]
    for _previous_time, new_time, new_digit in brackets:
        frames = [
            (new_time + index / 50, new_digit)
            for index in range(search.LAP_DIGIT_HOLD_FRAMES)
        ]
        assert search.held_lap_start_time(frames, new_digit) == new_time


def test_lap_digit_match_accepts_distance_four_and_rejects_five():
    near = search.lap_digit_template(2).copy()
    flat = near.reshape(-1)
    flat[:4] = ~flat[:4]
    assert search.lap_digit_distance(near, search.lap_digit_template(2)) == 4
    assert search.match_lap_digit(near) == 2

    flat[4] = ~flat[4]
    assert search.lap_digit_distance(near, search.lap_digit_template(2)) == 5
    assert search.match_lap_digit(near) is None


def test_lap_brackets_from_digits():
    assert search.lap_brackets_from_digits([(10, 0), (15, 1)]) == [(10, 15, 1)]
    assert search.lap_brackets_from_digits([(100, 3), (106, 3)]) == []
    assert search.lap_brackets_from_digits([(0, None), (200, 1)]) == []
    assert search.lap_brackets_from_digits([(10, 1), (40, None), (50, 2)]) == []
    assert search.lap_brackets_from_digits([(10, 2), (16, 3)]) == [(10, 16, 3)]
    assert search.lap_brackets_from_digits([(10, 3), (16, 0)]) == []


def test_one_missed_keyframe_still_brackets_the_step():
    samples = [(10, 0), (15, None), (20, 1)]
    assert search.lap_brackets_from_digits(samples) == [(10, 20, 1)]


def test_five_frame_hold_returns_the_first_frame_of_the_run():
    frames = [(0.0, 1), (0.1, 2), (0.2, 2), (0.3, 2), (0.4, 2)]
    assert search.held_lap_start_time(frames, 2) is None
    frames.append((0.5, 2))
    assert search.held_lap_start_time(frames, 2) == 0.1


def test_single_frame_digit_blip_is_not_a_hold():
    frames = [(0.0, 1), (0.1, 2), (0.2, 1)]
    assert search.held_lap_start_time(frames, 2) is None


def test_lap_letter_presence():
    assert search.is_lap_letter_present(107, 0.82) is True
    assert search.is_lap_letter_present(0, 0.82) is False
    assert search.is_lap_letter_present(240, 0.82) is False
    assert search.is_lap_letter_present(313, 0.18) is False


def test_lap_crop_at_reference_size():
    assert search.lap_crop_for_frame(1920, 1080) == (80, 28, 164, 128)


def test_showinfo_pts_times_ignores_other_lines():
    stderr = "\n".join([
        "frame=1 fps=0.0",
        "[Parsed_showinfo_1 @ 0x1] n:   0 pts:  100 pts_time:280.78 duration: 1001",
        "side data pts_time:1.0",
        "[Parsed_showinfo_1 @ 0x1] n:   1 pts_time:374.37",
    ])
    assert search.showinfo_pts_times(stderr) == [280.78, 374.37]
