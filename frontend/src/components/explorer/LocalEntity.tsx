import { useMutation } from "@tanstack/react-query";
import { Laptop, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getLocal, removeLocal, updateNote } from "@/lib/localTerms";

/** A term kept on this device only: it was not verified, so it is not in the shared catalogue and is never sent anywhere. */
export function LocalEntity({
  id,
  onOpen,
  onHome,
}: {
  id: string;
  onOpen: (id: string) => void;
  onHome: () => void;
}) {
  const [term, setTerm] = useState(() => getLocal(id));
  const [note, setNote] = useState(term?.note ?? "");
  const [saved, setSaved] = useState(false);
  const recheck = useMutation({ mutationFn: (label: string) => api.lookup(label) });
  if (!term) {
    return (
      <div className="mx-auto max-w-xl p-10 text-center">
        <h1 className="text-xl font-semibold">Nothing saved here</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This term was only ever kept in the browser it was saved in, and it is not there now.
        </p>
        <Button className="mt-4" onClick={onHome}>
          Back to search
        </Button>
      </div>
    );
  }
  const result = recheck.data;
  return (
    <div className="mx-auto max-w-2xl px-5 py-10">
      <span className="entity-type">
        <Laptop className="mr-1 size-3" /> on this device only
      </span>
      <h1 className="mt-4 text-2xl font-semibold">{term.label}</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Saved {term.created}. It could not be verified as a medical term, so it is <b>not</b> in the
        shared catalogue, has no evidence behind it and is not sent anywhere. Reason: {term.reason}.
      </p>
      <label className="mt-6 block text-xs font-semibold" htmlFor="local-note">
        Your private note
      </label>
      <textarea
        id="local-note"
        value={note}
        onChange={(e) => {
          setNote(e.target.value);
          setSaved(false);
        }}
        rows={5}
        maxLength={2000}
        className="mt-2 w-full border border-border bg-background p-3 text-sm"
        placeholder="Anything you want to remember about this term. Kept in this browser only. Do not include patient identifiers."
      />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() => {
            updateNote(id, note);
            setTerm(getLocal(id));
            setSaved(true);
          }}
        >
          Save note
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={recheck.isPending}
          onClick={() => recheck.mutate(term.label)}
        >
          <RefreshCw className={recheck.isPending ? "animate-spin" : ""} /> Check it against public
          sources again
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            removeLocal(id);
            onHome();
          }}
        >
          <Trash2 /> Delete
        </Button>
      </div>
      {saved && (
        <p role="status" className="mt-2 text-xs text-reviewed">
          Saved on this device.
        </p>
      )}
      {result?.status === "added" && (
        <p role="status" className="mt-4 text-sm">
          Verified this time:{" "}
          <button
            className="font-semibold underline"
            onClick={() => {
              removeLocal(id);
              onOpen(result.entity_id);
            }}
          >
            open {result.label} in the shared catalogue
          </button>
          .
        </p>
      )}
      {result?.status === "known" && (
        <p role="status" className="mt-4 text-sm">
          It is in the catalogue now:{" "}
          <button
            className="font-semibold underline"
            onClick={() => {
              removeLocal(id);
              onOpen(result.results[0]?.id ?? "");
            }}
          >
            open it
          </button>
          .
        </p>
      )}
      {result && !["added", "known"].includes(result.status) && (
        <p role="status" className="mt-4 text-xs text-muted-foreground">
          Still not verified. {"reason" in result ? result.reason : ""}
        </p>
      )}
    </div>
  );
}
