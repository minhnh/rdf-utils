# SPDX-License-Identifier: MPL-2.0
from rdflib import Graph, URIRef
from rdf_utils.models.common import ModelBase
from rdf_utils.models.vocab import (
    URI_EL_PRED_HAS_EVT,
    URI_EL_PRED_HAS_EVT_REACT,
    URI_EL_PRED_HAS_FLG,
    URI_EL_PRED_HAS_FLG_REACT,
    URI_EL_PRED_REF_EVT,
    URI_EL_PRED_REF_FLG,
)


class EventReactionModel(ModelBase):
    """Model for reactions to an event.

    Attributes:
        event_id: URI of the event to react to

    Parameters:
        reaction_id: URI of the reaction model
        graph: RDF graph to load relevant attributes
    """

    event_id: URIRef

    def __init__(self, reaction_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=reaction_id, graph=graph)

        evt_uri = graph.value(subject=self.id, predicate=URI_EL_PRED_REF_EVT)
        assert evt_uri is not None and isinstance(evt_uri, URIRef), (
            f"EventReaction '{self.id}' does not refer to a valid event URI: {evt_uri}"
        )
        self.event_id = evt_uri


class FlagReactionModel(ModelBase):
    """Model for reactions to a flag.

    Attributes:
        flag_id: URI of the flag to react to

    Parameters:
        reaction_id: URI of the reaction model
        graph: RDF graph to load relevant attributes
    """

    flag_id: URIRef

    def __init__(self, reaction_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=reaction_id, graph=graph)

        flg_uri = graph.value(subject=self.id, predicate=URI_EL_PRED_REF_FLG)
        assert flg_uri is not None and isinstance(flg_uri, URIRef), (
            f"FlagReaction '{self.id}' does not refer to a valid flag URI: {flg_uri}"
        )
        self.flag_id = flg_uri


class EventLoopModel(ModelBase):
    """Model of an event loop containing models of reactions to events and flags.

    Attributes:
        events_triggered: if true should notify that an event is triggered in the last loop
        flag_values: value of flag in the last loop
        event_reactions: reaction models to events
        flag_reactions: reaction models to flags

    Parameters:
        el_id: URI of event loop
        graph: graph for loading attributes
    """

    events_triggered: dict[URIRef, bool]
    flag_values: dict[URIRef, bool]
    event_reactions: dict[URIRef, EventReactionModel]
    flag_reactions: dict[URIRef, FlagReactionModel]
    event_reaction_maps: dict[URIRef, set[URIRef]]
    flag_reaction_maps: dict[URIRef, set[URIRef]]

    def __init__(self, el_id: URIRef, graph: Graph) -> None:
        super().__init__(node_id=el_id, graph=graph)

        self.events_triggered = {}
        self.flag_values = {}
        self.event_reactions = {}
        self.event_reaction_maps = {}
        self.flag_reactions = {}
        self.flag_reaction_maps = {}

        for evt_uri in graph.objects(subject=self.id, predicate=URI_EL_PRED_HAS_EVT):
            assert isinstance(evt_uri, URIRef), (
                f"Event '{evt_uri}' is not of type URIRef: {type(evt_uri)}"
            )
            self.events_triggered[evt_uri] = False

        for flg_uri in graph.objects(subject=self.id, predicate=URI_EL_PRED_HAS_FLG):
            assert isinstance(flg_uri, URIRef), (
                f"Flag '{flg_uri}' is not of type URIRef: {type(flg_uri)}"
            )
            self.flag_values[flg_uri] = False

        for evt_re_uri in graph.objects(subject=self.id, predicate=URI_EL_PRED_HAS_EVT_REACT):
            assert isinstance(evt_re_uri, URIRef), (
                f"EventReaction '{evt_re_uri}' is not of type URIRef: {type(evt_re_uri)}"
            )
            evt_re_model = EventReactionModel(reaction_id=evt_re_uri, graph=graph)
            assert evt_re_model.event_id in self.events_triggered, (
                f"'{evt_re_model.id}' reacts to event '{evt_re_model.event_id}', which is not in event loop '{self.id}'"
            )
            self.event_reactions[evt_re_model.id] = evt_re_model
            evt_id = evt_re_model.event_id
            if evt_id not in self.event_reaction_maps:
                self.event_reaction_maps[evt_id] = set()
            self.event_reaction_maps[evt_id].add(evt_re_model.id)

        for flg_re_uri in graph.objects(subject=self.id, predicate=URI_EL_PRED_HAS_FLG_REACT):
            assert isinstance(flg_re_uri, URIRef), (
                f"FlagReaction '{flg_re_uri}' is not of type URIRef: {type(flg_re_uri)}"
            )
            flg_re_model = FlagReactionModel(reaction_id=flg_re_uri, graph=graph)
            assert flg_re_model.flag_id in self.flag_values, (
                f"'{flg_re_model.id}' reacts to flag '{flg_re_model.flag_id}', which is not in event loop '{self.id}'"
            )
            self.flag_reactions[flg_re_model.id] = flg_re_model
            flag_id = flg_re_model.flag_id
            if flag_id not in self.flag_reaction_maps:
                self.flag_reaction_maps[flag_id] = set()
            self.flag_reaction_maps[flag_id].add(flg_re_model.id)
