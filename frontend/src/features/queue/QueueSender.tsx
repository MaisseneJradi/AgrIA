import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useOnline } from "@/lib/useOnline";
import { useDiagnosis } from "../diagnosis/store";
import { STEP_PATH } from "../diagnosis/steps";
import { clearPending, getPending } from "./queue";

/** When the network comes back (or the app opens with network) and a photo was put aside with the farmer's consent:
 * its analysis is asked now, and the answer screen says when the photo had been put aside. */
export function QueueSender() {
  const online = useOnline();
  const navigate = useNavigate();
  const busy = useRef(false);
  useEffect(() => {
    if (!online || busy.current) return;
    busy.current = true;
    void getPending()
      .then(async (p) => {
        if (!p) return;
        await clearPending();
        useDiagnosis.setState({
          photo: p.photo,
          identify: null,
          crop: p.crop,
          message: p.message,
          gouvernorat: p.gouvernorat,
          context: p.context,
          answer: null,
          queuedFrom: p.date,
        });
        useDiagnosis.getState().submit();
        navigate(STEP_PATH.answer);
      })
      .finally(() => {
        busy.current = false;
      });
  }, [online, navigate]);
  return null;
}
