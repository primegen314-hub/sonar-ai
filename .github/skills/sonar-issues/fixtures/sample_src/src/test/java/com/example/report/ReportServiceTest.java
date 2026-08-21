package com.example.report;

import java.util.List;

/** Fixture test file so s05 can demonstrate test discovery. */
public class ReportServiceTest {

    public void countRowsReturnsZeroForNull() {
        ReportService service = new ReportService();
        assert service.countRows(null) == 0;
    }

    public void countRowsCountsEntries() {
        ReportService service = new ReportService();
        assert service.countRows(List.of("a", "b")) == 2;
    }
}
