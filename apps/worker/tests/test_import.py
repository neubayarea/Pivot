from pivot_worker.__main__ import main


def test_main_runs(capsys):
    main()
    assert "pivot-worker" in capsys.readouterr().out
