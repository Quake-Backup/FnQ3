from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CinematicInputSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "code" / "client" / "cl_cin.cpp").read_text(
            encoding="utf-8"
        )

    def function(self, signature: str, next_signature: str) -> str:
        start = self.source.index(signature)
        end = self.source.index(next_signature, start + len(signature))
        return self.source[start:end]

    def test_bootstrap_and_chunk_reads_are_validated_before_use(self) -> None:
        header = self.function("static bool RoQReadHeader", "static void RoQReset")
        interrupt = self.function("static void RoQInterrupt", "static bool RoQ_init")

        self.assertLess(header.index("FileRead("), header.index("RoQFileHeaderReadComplete"))
        self.assertIn("roqId == ROQ_FILE_ID && RoQ_init()", header)

        payload_guard = interrupt.index("RoQPayloadFits(")
        read_plan = interrupt.index("RoQPlanRead(")
        plan_guard = interrupt.index("RoQReadPlanIsValid(")
        payload_read = interrupt.index("bytesRead = FileRead(")
        read_result = interrupt.index("RoQReadComplete(")
        decode_loop = interrupt.index("for (;;) {")
        self.assertLess(payload_guard, read_plan)
        self.assertLess(read_plan, plan_guard)
        self.assertLess(plan_guard, payload_read)
        self.assertLess(payload_read, read_result)
        self.assertLess(read_result, decode_loop)

    def test_terminal_payload_is_decoded_before_deferred_end_handling(self) -> None:
        finish = self.function("static void RoQFinishPendingEnd", "static void RoQInterrupt")
        interrupt = self.function("static void RoQInterrupt", "static bool RoQ_init")

        hold = finish.index("holdAtEnd")
        loop = finish.index("looping")
        eof = finish.index("status = FMV_EOF")
        self.assertLess(hold, loop)
        self.assertLess(loop, eof)

        payload_read = interrupt.index("bytesRead = FileRead(")
        decode = interrupt.index("switch(cinTable[currentHandle].roq_id)")
        packet_complete = interrupt.index(
            "frameOffset != packetPayloadEnd"
        )
        mark_pending = interrupt.index("eofPending = true;")
        external_header = interrupt.index(
            "cinTable[currentHandle].roq_id\t\t = framedata[0]"
        )
        self.assertLess(payload_read, decode)
        self.assertLess(decode, packet_complete)
        self.assertLess(packet_complete, mark_pending)
        self.assertLess(mark_pending, external_header)
        self.assertIn("terminalChunk && !embeddedHeader", interrupt)

        run = self.function("e_status CIN_RunCinematic", "int CIN_PlayCinematic")
        pending_finish = run.index("RoQFinishPendingEnd();")
        decode_call = run.index("RoQInterrupt();")
        pending_break = run.index("if ( cinTable[currentHandle].eofPending )", decode_call)
        self.assertLess(pending_finish, decode_call)
        self.assertLess(decode_call, pending_break)
        self.assertLess(pending_break, run.index("break;", pending_break))

    def test_packet_and_audio_paths_use_explicit_capacity_boundaries(self) -> None:
        interrupt = self.function("static void RoQInterrupt", "static bool RoQ_init")

        self.assertIn("std::size_t packetPayloadEnd = 0;", interrupt)
        self.assertGreaterEqual(interrupt.count("RoQRangeFits("), 4)
        self.assertIn("frameOffset != packetPayloadEnd", interrupt)
        self.assertIn("RoQStereoPayloadIsPaired(", interrupt)
        self.assertIn("RllDecodeMonoToStereo( framedata, cin.sound.data()", interrupt)
        self.assertNotIn("std::array<short, 32768> sbuf", interrupt)

    def test_quad_info_is_sized_and_bounded_before_geometry_setup(self) -> None:
        quad_info = self.function("static bool readQuadInfo", "static void RoQPrepMcomp")
        interrupt = self.function("static void RoQInterrupt", "static bool RoQ_init")
        quad_case = interrupt[
            interrupt.index("case\tROQ_QUAD_INFO:") : interrupt.index(
                "case\tROQ_PACKET:"
            )
        ]

        payload_guard = quad_info.index("payloadBytes != kRoQQuadInfoBytes")
        dimension_read = quad_info.index("qData[0]")
        geometry_guard = quad_info.index("RoQQuadInfoIsValid(")
        self.assertLess(payload_guard, dimension_read)
        self.assertLess(dimension_read, geometry_guard)

        size_check = quad_case.index("RoQFrameSize != kRoQQuadInfoBytes")
        decode = quad_case.index("readQuadInfo(")
        setup = quad_case.index("setupQuad(")
        self.assertLess(size_check, decode)
        self.assertLess(decode, setup)

    def test_codebook_and_vq_decoders_validate_their_declared_payloads(self) -> None:
        validator = self.function(
            "static bool RoQVQPayloadIsValid", "static bool blitVQQuad32fs"
        )
        decoder = self.function(
            "static bool blitVQQuad32fs", "static void ROQ_GenYUVTables"
        )
        interrupt = self.function("static void RoQInterrupt", "static bool RoQ_init")
        vq_case = interrupt[
            interrupt.index("case\tROQ_QUAD_VQ:") : interrupt.index(
                "case\tROQ_CODEBOOK:"
            )
        ]
        codebook_case = interrupt[
            interrupt.index("case\tROQ_CODEBOOK:") : interrupt.index(
                "case\tZA_SOUND_MONO:"
            )
        ]

        self.assertIn("RoQByteReader reader( data, dataBytes )", validator)
        self.assertIn("reader.ReadLittleShort(", validator)
        self.assertIn("reader.ReadByte(", validator)
        self.assertIn("kRoQStatusCapacity", validator)
        self.assertIn("RoQBlockFits(", validator)
        self.assertLess(
            decoder.index("RoQVQPayloadIsValid("), decoder.index("data[0]")
        )

        geometry_guard = vq_case.index("quadInfoValid")
        decode_call = vq_case.index("VQ1(")
        self.assertLess(geometry_guard, decode_call)
        self.assertIn("RoQFrameSize", vq_case[decode_call:])

        plan = codebook_case.index("RoQPlanCodebook(")
        plan_guard = codebook_case.index("codebookPlan.valid")
        codebook_decode = codebook_case.index("decodeCodeBook(")
        self.assertLess(plan, plan_guard)
        self.assertLess(plan_guard, codebook_decode)

    def test_header_failures_release_files_and_slots(self) -> None:
        reset = self.function("static void RoQReset", "static void RoQInterrupt")
        shutdown = self.function("static void RoQShutdown", "e_status CIN_StopCinematic")
        run = self.function("e_status CIN_RunCinematic", "int CIN_PlayCinematic")
        play = self.function("int CIN_PlayCinematic", "void CIN_SetExtents")

        self.assertIn("cinTable[currentHandle].iFile.reset();", reset)
        self.assertIn("cinTable[currentHandle].fileName[0] = '\\0';", reset)
        self.assertIn("cinTable[currentHandle].looping = false;", reset)
        self.assertNotIn("if (!cinTable[currentHandle].buf)", shutdown)

        successful_header = play.index("if ( RoQReadHeader() )")
        play_state = play.index("status = FMV_PLAY")
        failure_cleanup = play.index("cinTable[currentHandle].iFile.reset();", play_state)
        self.assertLess(successful_header, play_state)
        self.assertGreater(failure_cleanup, play_state)
        self.assertIn("currentHandle = -1;", play[failure_cleanup:])

        eof_branch = run[run.rindex("if (cinTable[currentHandle].status == FMV_EOF)") :]
        reset_call = eof_branch.index("RoQReset();")
        reset_result = eof_branch.index(
            "if (cinTable[currentHandle].status != FMV_EOF)"
        )
        shutdown_call = eof_branch.index("RoQShutdown();")
        self.assertLess(reset_call, reset_result)
        self.assertLess(reset_result, shutdown_call)

    def test_first_frame_wait_rechecks_the_public_handle_before_indexing(self) -> None:
        command = self.function("void CL_PlayCinematic_f", "void SCR_DrawCinematic")
        wait = command[command.index("do {") :]

        lower_guard = wait.index("CL_handle >= 0")
        upper_guard = wait.index("CL_handle < MAX_VIDEO_HANDLES")
        table_access = wait.index("cinTable[CL_handle]")
        self.assertLess(lower_guard, upper_guard)
        self.assertLess(upper_guard, table_access)
        self.assertNotIn("cinTable[currentHandle]", wait)

    def test_large_decode_state_is_cleared_in_place(self) -> None:
        play = self.function("int CIN_PlayCinematic", "void CIN_SetExtents")

        self.assertIn("Com_Memset( &cin, 0, sizeof( cin ) );", play)
        self.assertNotIn("cin = {};", play)


if __name__ == "__main__":
    unittest.main()
